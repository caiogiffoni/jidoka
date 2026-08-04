"""LangGraph state machine for the HITL create_task agent.

Flow: agent (LLM) -> tools (create_task proposals) -> propose (human interrupt)
-> apply (persist if approved) or end (if rejected).
"""

import os
import uuid
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

import db
from agent.state import AgentState, CreateTaskChange, ProposedDiff
from agent.tools import create_task as _create_task
from models import TaskCreate
from services import create_task_service


@tool("create_task")
def create_task_tool(
    title: str,
    description: str | None = None,
    column_id: str = "todo",
    project_id: str | None = None,
    checklist: list[dict] | None = None,
) -> dict:
    """Propose creating a new task on the board."""
    return _create_task(
        title=title,
        description=description,
        column_id=column_id,
        project_id=project_id,
        checklist=checklist,
    )


# Module-level model used by the SSE endpoint. Tests patch this directly.
model = None


def _default_model():
    """Lazy factory for the production LLM routed through OpenRouter."""
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        model=os.environ.get("OPENROUTER_MODEL") or "openai/gpt-4o-mini",
    ).bind_tools([create_task_tool])


def _resolve_model(explicit_model):
    if explicit_model is not None:
        return explicit_model
    if model is not None:
        return model
    return _default_model()


def _extract_tool_calls(message: AIMessage) -> list[dict[str, Any]]:
    """Normalize tool_calls from both real LLMs and the test fake."""
    raw = getattr(message, "tool_calls", [])
    normalized = []
    for tc in raw:
        if "function" in tc:
            # FakeToolCallingModel shape: {"id": ..., "function": {"name": ..., "arguments": ...}}
            normalized.append(
                {
                    "id": tc.get("id", "call_1"),
                    "name": tc["function"]["name"],
                    "args": tc["function"]["arguments"],
                }
            )
        else:
            # Standard LangChain shape: {"id": ..., "name": ..., "args": ...}
            normalized.append(tc)
    return normalized


def _session_from_config(config: RunnableConfig):
    """Return the session passed in config, or open a new one from the engine."""
    session = config.get("configurable", {}).get("session")
    if session is not None:
        return session
    return next(db.get_session())


def build_graph(model=None):
    """Build and compile the HITL agent graph."""
    # Model resolution is deferred to agent_node so importing this module does
    # not require OPENROUTER_API_KEY. Tests pass a fake model explicitly; production
    # resolves the module-level `model` global or falls back to ChatOpenAI.
    explicit_model = model

    def agent_node(state: AgentState, config: RunnableConfig) -> dict:
        llm = explicit_model if explicit_model is not None else _resolve_model(None)
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    def tool_node(state: AgentState, config: RunnableConfig) -> dict:
        last_message = state["messages"][-1]
        tool_calls = _extract_tool_calls(last_message)

        changes: list[CreateTaskChange] = []
        tool_messages: list[ToolMessage] = []

        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args", {})
            if name != "create_task":
                raise ValueError(f"unsupported tool: {name}")
            result = _create_task(**args)
            changes.append(CreateTaskChange(**result))
            tool_messages.append(
                ToolMessage(content="proposed", tool_call_id=tc.get("id", "call_1"))
            )

        return {"messages": tool_messages, "proposed_changes": changes}

    def propose_node(state: AgentState, config: RunnableConfig) -> dict:
        diff = ProposedDiff(changes=state.get("proposed_changes", []))
        decision = interrupt({"diff": diff})
        approved = bool(decision.get("approved")) if isinstance(decision, dict) else False
        return {"approved": approved}

    def apply_node(state: AgentState, config: RunnableConfig) -> dict:
        if not state.get("approved"):
            return {"applied_results": []}

        user_id = uuid.UUID(config["configurable"]["user_id"])
        session = _session_from_config(config)
        own_session = config.get("configurable", {}).get("session") is None

        try:
            created: list = []
            for change in state.get("proposed_changes", []):
                task = create_task_service(
                    session,
                    user_id,
                    TaskCreate(
                        title=change.title,
                        description=change.description,
                        column_id=change.column_id,
                        project_id=change.project_id,
                        checklist=change.checklist,
                    ),
                )
                created.append(task)
            return {"applied_results": created}
        finally:
            if own_session:
                session.close()

    def route_after_agent(state: AgentState) -> str:
        last = state["messages"][-1]
        if _extract_tool_calls(last):
            return "tools"
        return END

    def route_after_propose(state: AgentState) -> str:
        if state.get("approved"):
            return "apply"
        return END

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("propose", propose_node)
    builder.add_node("apply", apply_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route_after_agent)
    builder.add_edge("tools", "propose")
    builder.add_conditional_edges("propose", route_after_propose)
    builder.add_edge("apply", END)

    from langgraph.checkpoint.memory import MemorySaver

    return builder.compile(checkpointer=MemorySaver())


# Default graph instance used by the SSE endpoint. The model is resolved lazily
# inside agent_node, so importing this module does not require OPENROUTER_API_KEY.
graph = build_graph(model=None)
