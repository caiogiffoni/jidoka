"""LangGraph state machine for the HITL create_task agent.

Flow: agent (LLM) -> tools (create_task proposals) -> propose (human interrupt)
-> apply (persist if approved) or end (if rejected).
"""

import os
import re
import uuid
from typing import Any

import db
from agent.state import AgentState, CreateTaskChange, ProposedDiff
from agent.tools import create_task as _create_task
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from models import TaskCreate
from services import create_task_service


@tool("create_task")
def create_task_tool(
    title: str,
    column_id: str,
    description: str | None = None,
    project_id: str | None = None,
    checklist: list[dict] | None = None,
) -> dict:
    """Propose creating a new task on the board."""
    return _create_task(
        title=title,
        column_id=column_id,
        description=description,
        project_id=project_id,
        checklist=checklist,
    )


# Module-level model used by the SSE endpoint. Tests patch this directly.
model = None

_SYSTEM_PROMPT = (
    "You are a focused kanban assistant. Your only job is to create tasks on the board. "
    "You have one tool: create_task(title, column_id). "
    "Valid column_id values are: backlog, todo, in_progress, done. "
    "\n\n"
    "CRITICAL RULES:\n"
    "1. You can see the full conversation history. Remember everything the user already told you. "
    "   NEVER ask for information the user already provided in this conversation.\n"
    "2. If the user provides both a title and a column in the same message, call create_task immediately. "
    "   Do not confirm, do not ask again.\n"
    "3. If the user gives you only the title, confirm the title you understood and ask only for the column.\n"
    "4. If the user gives you only the column, confirm the column you understood and ask only for the title.\n"
    "5. If you already know the title and the user gives you the missing column, call create_task immediately.\n"
    "6. If you already know the column and the user gives you the missing title, call create_task immediately.\n"
    "7. If the user also provides a description or checklist items, include them. Otherwise do not ask for them.\n"
    "8. Stay focused on kanban tasks. Politely decline off-topic questions.\n"
    "\n"
    "Examples of correct behavior:\n"
    "- User: 'Create a task Read docs in todo' → call create_task(title='Read docs', column_id='todo')\n"
    "- User: 'Add Buy milk' → reply 'Got it, title is Buy milk. Which column? (backlog, todo, in_progress, done)'\n"
    "- Assistant asked for column. User: 'todo' → call create_task with the known title and column_id='todo'\n"
    "- Assistant asked for title. User: 'Read docs' → call create_task with title='Read docs' and the known column\n"
    "- User: 'Who is the president?' → reply 'I'm here to help with your kanban board. What task can I create for you?'"
)


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


def _task_tool_call_message(draft: dict, title: str, column_id: str) -> AIMessage:
    """Build an AIMessage that calls create_task with the given fields."""
    return AIMessage(
        content="",
        tool_calls=[
            {
                "id": "call_1",
                "name": "create_task",
                "args": {
                    "title": title,
                    "column_id": column_id,
                    "description": draft.get("description"),
                    "checklist": draft.get("checklist"),
                },
            }
        ],
    )


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


_VALID_COLUMNS = {"backlog", "todo", "in_progress", "done"}


_QUOTE_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'')

_TASK_REQUEST_RE = re.compile(r"\b(create|add|make|new)\b", re.IGNORECASE)

_TITLE_CLEANUP_RE = re.compile(
    r"^\s*(create|add|make|new)\s+(a\s+)?(task\s*)?"
    r"|\s+in\s+(backlog|todo|in_progress|done)\s*$"
    r"|^\s*(in\s+)?(backlog|todo|in_progress|done)\s*$",
    re.IGNORECASE,
)


def _extract_quoted_title(text: str) -> str | None:
    """Return the first quoted substring in the text, if any."""
    match = _QUOTE_RE.search(text)
    if match:
        return (match.group(1) or match.group(2)).strip()
    return None


def _detect_column(text: str) -> str | None:
    """Return the first valid column id found as a whole word, or None."""
    lowered = text.lower()
    for column in _VALID_COLUMNS:
        if column in lowered:
            return column
    return None


def _extract_latest_user_text(messages: list) -> str:
    """Return the content of the most recent user message, or an empty string."""
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "human" or (
            isinstance(msg, dict) and msg.get("role") == "user"
        ):
            return str(
                msg.content if hasattr(msg, "content") else msg.get("content", "")
            ).strip()
    return ""


def _looks_like_task_request(text: str) -> bool:
    """Return True if the user seems to be asking to create a task."""
    return bool(_TASK_REQUEST_RE.search(text))


def _clean_title(text: str, column: str | None) -> str:
    """Strip task-request filler and the column word from an unquoted title."""
    title = text
    if column:
        title = re.sub(
            r"\b" + re.escape(column) + r"\b", "", title, flags=re.IGNORECASE
        )
    title = _TITLE_CLEANUP_RE.sub("", title)
    title = re.sub(r"^\s*(to|for|about)\s+", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+in\s*$", "", title, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", title).strip()


def _parse_message(text: str) -> dict:
    """Extract title and/or column from a single user message.

    Returns a dict with zero or more of: title, column_id.
    """
    result: dict[str, Any] = {}
    text = str(text).strip()
    lowered = text.lower()

    column = _detect_column(text)
    if column is not None:
        result["column_id"] = column
        # If the whole message is just the column, don't treat it as a title.
        if lowered == column:
            return result

    quoted = _extract_quoted_title(text)
    if quoted:
        result["title"] = quoted
    else:
        cleaned = _clean_title(text, column)
        if cleaned:
            result["title"] = cleaned

    return result


def _update_draft(draft: dict | None, messages: list) -> dict:
    """Accumulate title/column from the latest user message into the draft."""
    updated = dict(draft) if draft else {}
    parsed = _parse_message(_extract_latest_user_text(messages))
    if "title" in parsed:
        updated["title"] = parsed["title"]
    if "column_id" in parsed:
        updated["column_id"] = parsed["column_id"]
    return updated


def _build_context_messages(draft: dict, latest_user_text: str) -> list:
    """Build a focused LLM context from the draft and latest user message."""
    known_parts = []
    if draft.get("title"):
        known_parts.append(f"title: {draft['title']}")
    if draft.get("column_id"):
        known_parts.append(f"column: {draft['column_id']}")

    memory = "We are creating a kanban task."
    if known_parts:
        memory += " Already known: " + ", ".join(known_parts) + "."
    memory += (
        " Use the create_task tool when you have both the title and the column. "
        "If one is missing, ask only for the missing one. "
        "Do not ask for information already listed above."
    )

    return [
        SystemMessage(content=_SYSTEM_PROMPT),
        SystemMessage(content=memory),
        SystemMessage(content=f"Latest user message: {latest_user_text}"),
    ]


def build_graph(model=None):
    """Build and compile the HITL agent graph."""
    # Model resolution is deferred to agent_node so importing this module does
    # not require OPENROUTER_API_KEY. Tests pass a fake model explicitly; production
    # resolves the module-level `model` global or falls back to ChatOpenAI.
    explicit_model = model

    def agent_node(state: AgentState, config: RunnableConfig) -> dict:
        old_draft = state.get("draft") or {}
        draft = _update_draft(old_draft, state["messages"])

        had_title_before = bool(old_draft.get("title"))
        had_column_before = bool(old_draft.get("column_id"))

        latest_text = _extract_latest_user_text(state["messages"])
        latest_parsed = _parse_message(latest_text)

        # Deterministic handling for common single-intent task requests. This avoids
        # small-model hallucinations like proposing a column that was never given.
        if _looks_like_task_request(latest_text):
            user_title = latest_parsed.get("title")
            user_column = latest_parsed.get("column_id")

            # User gave both pieces in one message -> create immediately.
            if user_title and user_column:
                return {
                    "messages": [
                        _task_tool_call_message(draft, user_title, user_column)
                    ],
                    "draft": draft,
                }

            # User gave only the title -> confirm and ask for the column.
            if user_title and not user_column:
                return {
                    "messages": [
                        AIMessage(
                            content=f'Got it, title is "{user_title}". Which column? (backlog, todo, in_progress, done)'
                        )
                    ],
                    "draft": draft,
                }

            # User gave only the column -> confirm and ask for the title.
            if user_column and not user_title:
                return {
                    "messages": [
                        AIMessage(
                            content=f"Got it, column is {user_column}. What's the title?"
                        )
                    ],
                    "draft": draft,
                }

        # If we already knew one piece and the user just supplied the missing one,
        # call the tool directly. This avoids instruction-following loops with
        # small models on the second turn.
        if (
            draft.get("title")
            and draft.get("column_id")
            and (had_title_before or had_column_before)
        ):
            response = _task_tool_call_message(
                draft, draft["title"], draft["column_id"]
            )
            return {"messages": [response], "draft": draft}

        # Fall back to the LLM for off-topic handling, ambiguous input, or when
        # the user did not provide a clear title or column.
        llm = explicit_model if explicit_model is not None else _resolve_model(None)
        messages = _build_context_messages(draft, latest_text)
        response = llm.invoke(messages)
        return {"messages": [response], "draft": draft}

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
            return {"applied_results": [], "draft": None}

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
            return {"applied_results": created, "draft": None}
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
