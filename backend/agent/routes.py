"""SSE endpoint for the HITL agent.

The frontend opens an EventSource to /agent/stream. The backend streams
message / tool_call / interrupt / apply / error / done events.
"""

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from pydantic import BaseModel
from sqlmodel import Session

import auth
from agent.graph import graph
from agent.state import ProposedDiff
from db import get_session
from models import User

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentStreamRequest(BaseModel):
    thread_id: str
    message: str | None = None
    resume: dict | None = None


def _format_sse(event: str, data: Any) -> str:
    """Serialize one SSE event block."""
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _translate_chunk(chunk: dict) -> list[tuple[str, Any]]:
    """Translate a LangGraph update chunk into SSE event tuples.

    If the chunk is already an event dict (from mocked tests), pass it through.
    Otherwise interpret LangGraph node updates.
    """
    if "event" in chunk and "data" in chunk:
        return [(chunk["event"], chunk["data"])]

    events = []
    for node, update in chunk.items():
        if node == "agent":
            messages = update.get("messages", [])
            for msg in messages:
                if isinstance(msg, AIMessage):
                    if getattr(msg, "tool_calls", None):
                        for tc in msg.tool_calls:
                            name = tc.get("name") or tc.get("function", {}).get("name")
                            args = tc.get("args") or tc.get("function", {}).get("arguments", {})
                            events.append(("tool_call", {"name": name, "arguments": args}))
                    else:
                        events.append(("message", {"role": "assistant", "content": msg.content}))
        elif node == "tools":
            changes = update.get("proposed_changes", [])
            if changes:
                events.append(("tool_call", {"changes": [c.model_dump() for c in changes]}))
        elif node == "propose":
            # Interrupt value is captured separately; this update just confirms
            # we reached the propose node.
            pass
        elif node == "apply":
            results = update.get("applied_results", [])
            events.append(("apply", {"created_tasks": [t.model_dump() for t in results]}))
        elif node == "__interrupt__":
            interrupt_value = update[0] if isinstance(update, (list, tuple)) else update
            if hasattr(interrupt_value, "value"):
                interrupt_value = interrupt_value.value
            diff = interrupt_value.get("diff") if isinstance(interrupt_value, dict) else interrupt_value
            if isinstance(diff, ProposedDiff):
                events.append(("interrupt", {"changes": [c.model_dump() for c in diff.changes]}))
            elif isinstance(diff, dict):
                events.append(("interrupt", diff))
    return events


@router.post("/stream")
def stream_agent(
    request: AgentStreamRequest,
    current_user: User = Depends(auth.get_current_user),
    session: Session = Depends(get_session),
):
    """Stream agent events for a single turn (new message or resume)."""
    config = {
        "configurable": {
            "thread_id": request.thread_id,
            "user_id": str(current_user.id),
            "session": session,
        }
    }

    if request.resume is not None:
        input_payload = Command(resume=request.resume)
    elif request.message is not None:
        input_payload = {"messages": [HumanMessage(content=request.message)]}
    else:
        raise HTTPException(status_code=422, detail="provide message or resume")

    def event_generator():
        try:
            for chunk in graph.stream(input_payload, config, stream_mode="updates"):
                for event, data in _translate_chunk(chunk):
                    yield _format_sse(event, data)
        except Exception as exc:
            yield _format_sse("error", {"message": str(exc)})
        finally:
            yield _format_sse("done", {})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
