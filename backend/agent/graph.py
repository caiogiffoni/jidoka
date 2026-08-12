"""LangGraph state machine for the HITL kanban agent.

Flow: agent (LLM) -> tools (execute reads or build mutation proposals) ->
propose (human interrupt) -> apply (persist if approved) or end (if rejected).

Read tools (list_tasks, list_projects, get_task) execute immediately and return
ToolMessages to the agent. Mutation tools (create_task, move_task) produce
proposed changes that require human approval before the apply node touches the DB.
"""

import json
import os
import uuid
from typing import Any

from sqlalchemy import select


def _json_safe(obj: Any) -> Any:
    """Return a JSON-serializable copy of a Pydantic model_dump dict.

    LangGraph's stream checkpoint serde can corrupt dicts that still contain
    UUID or datetime values when they pass through msgpack. Converting them to
    plain strings before returning avoids that corruption.
    """
    return json.loads(json.dumps(obj, default=str))

import db
from agent.state import (
    AgentState,
    BoardChange,
    CreateTaskChange,
    MoveTaskChange,
    ProposedDiff,
    UpdateTaskChange,
)
from agent.tools import (
    create_task_tool,
    get_task_tool,
    list_projects_tool,
    list_tasks_tool,
    move_task_tool,
    update_task_tool,
)
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from models import Project, TaskCreate, TaskUpdate
from services import (
    create_task_service,
    get_task_service,
    list_projects_service,
    list_tasks_service,
    move_task_service,
    update_task_service,
)


# Module-level model used by the SSE endpoint. Tests patch this directly.
model = None

_SYSTEM_PROMPT = (
    "You are a focused kanban assistant. You help users manage a kanban board.\n\n"
    "You have these tools:\n"
    "- create_task(title, column_id, description?, project_id?, checklist?)\n"
    "- move_task(task_id, column_id, position?)\n"
    "- update_task(task_id, title?, description?, project_id?, checklist?, due_date?)\n"
    "- list_tasks(column_id?, include_archived?, project_id?, project_name?)\n"
    "- list_projects()\n"
    "- get_task(task_id)\n\n"
    "CRITICAL RULES:\n"
    "1. Read the full conversation history. Remember everything the user already told you.\n"
    "2. create_task, move_task, and update_task REQUIRE human approval. They produce a proposed diff. "
    "Do not tell the user the change is done until they approve it.\n"
    "3. list_tasks, list_projects, and get_task return board data immediately. "
    "Use them whenever you need to know what exists on the board.\n"
    "4. If the user refers to a task by description (e.g. 'the top backlog item'), "
    "call list_tasks first to find the exact task_id. Never guess task ids.\n"
    "5. Valid column_id values are: backlog, todo, in_progress, done.\n"
    "6. Extract natural titles. Do NOT include filler words like 'create a task', "
    "'add', 'named', 'title is', or 'title =' in create_task titles.\n"
    "7. If the user gives both required pieces for create_task or move_task, call the tool immediately.\n"
    "8. If one piece is missing, ask only for the missing piece.\n"
    "9. If the user corrects you, accept the correction and use the corrected value.\n"
    "10. Stay focused on kanban tasks. Politely decline off-topic questions.\n\n"
    "Examples of correct behavior:\n"
    "- User: 'Create a task Read docs in todo' → create_task(title='Read docs', column_id='todo')\n"
    "- User: 'Move the top backlog item to todo' → list_tasks(column_id='backlog'), "
    "then move_task(task_id=<first id>, column_id='todo')\n"
    "- User: 'Update task abc123 description to Follow up tomorrow' → get_task(task_id='abc123'), "
    "then update_task(task_id='abc123', description='Follow up tomorrow')\n"
    "- User: 'What do I have in progress?' → list_tasks(column_id='in_progress'), then summarize\n"
    "- User: 'Move all tasks from project X to done' → list_tasks(project_name='X'), "
    "then call move_task once per returned task\n"
    "- User: 'Who is the president?' → 'I'm here to help with your kanban board. What can I do for you?'"
)


def _default_model():
    """Lazy factory for the production LLM routed through OpenRouter."""
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        model=os.environ.get("OPENROUTER_MODEL") or "openai/gpt-4o-mini",
    ).bind_tools([create_task_tool, move_task_tool, update_task_tool, list_tasks_tool, list_projects_tool, get_task_tool])


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


def _task_to_dict(task) -> dict:
    """Serialize a Task for read-tool results."""
    return {
        "id": str(task.id),
        "title": task.title,
        "column_id": task.column_id,
        "description": task.description,
        "project_id": str(task.project_id) if task.project_id else None,
        "project_name": task.project.name if task.project else None,
        "archived": task.archived,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "checklist": task.checklist or [],
    }


def _project_to_dict(project) -> dict:
    """Serialize a Project for read-tool results."""
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
    }


def _project_name(session, project_id: uuid.UUID | None) -> str | None:
    """Return a project's name, or None if the task has no project."""
    if project_id is None:
        return None
    project = session.get(Project, project_id)
    return project.name if project else None


def _resolve_project_name_to_id(
    session, user_id: uuid.UUID, project_name: str | None
) -> uuid.UUID | None:
    """Look up a project id by name for the current user.

    Returns None if no name is supplied or no matching project exists.
    """
    if project_name is None:
        return None
    from sqlalchemy import func

    project = session.exec(
        select(Project)
        .where(
            Project.user_id == user_id,
            func.lower(Project.name) == project_name.lower(),
        )
        .limit(1)
    ).scalars().first()
    return project.id if project else None


def build_graph(model=None):
    """Build and compile the HITL agent graph."""
    # Model resolution is deferred to agent_node so importing this module does
    # not require OPENROUTER_API_KEY. Tests pass a fake model explicitly; production
    # resolves the module-level `model` global or falls back to ChatOpenAI.
    explicit_model = model

    def agent_node(state: AgentState, config: RunnableConfig) -> dict:
        # The LLM sees the system prompt plus the full conversation history so it
        # can handle corrections, multi-turn clarification, and off-topic input.
        messages = [SystemMessage(content=_SYSTEM_PROMPT), *state["messages"]]

        llm = explicit_model if explicit_model is not None else _resolve_model(None)
        response = llm.invoke(messages)

        return {"messages": [response]}

    def tool_node(state: AgentState, config: RunnableConfig) -> dict:
        last_message = state["messages"][-1]
        tool_calls = _extract_tool_calls(last_message)

        changes: list[BoardChange] = []
        tool_messages: list[ToolMessage] = []
        session = _session_from_config(config)
        user_id = uuid.UUID(config["configurable"]["user_id"])

        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args", {})
            tool_call_id = tc.get("id", "call_1")

            if name == "create_task":
                result = create_task_tool.invoke(args)
                project_name = _project_name(session, result.get("project_id"))
                changes.append(
                    CreateTaskChange(**result, project_name=project_name)
                )
                tool_messages.append(
                    ToolMessage(content="proposed", tool_call_id=tool_call_id)
                )
            elif name == "move_task":
                parsed = move_task_tool.invoke(args)
                task = get_task_service(session, parsed["task_id"], user_id)
                changes.append(
                    MoveTaskChange(
                        task_id=task.id,
                        title=task.title,
                        from_column_id=task.column_id,
                        to_column_id=parsed["column_id"],
                        project_name=task.project.name if task.project else None,
                        position=parsed.get("position"),
                    )
                )
                tool_messages.append(
                    ToolMessage(content="proposed", tool_call_id=tool_call_id)
                )
            elif name == "update_task":
                parsed = update_task_tool.invoke(args)
                task = get_task_service(session, parsed["task_id"], user_id)
                project_id = parsed.get("project_id")
                if project_id is None:
                    project_id = task.project_id
                project_name = _project_name(session, project_id)
                changes.append(
                    UpdateTaskChange(
                        task_id=task.id,
                        title=parsed.get("title", task.title),
                        description=parsed.get("description", task.description),
                        project_id=project_id,
                        project_name=project_name,
                        checklist=parsed.get("checklist", task.checklist or []),
                        due_date=parsed.get("due_date", task.due_date),
                    )
                )
                tool_messages.append(
                    ToolMessage(content="proposed", tool_call_id=tool_call_id)
                )
            elif name == "list_tasks":
                filters = list_tasks_tool.invoke(args)
                project_id = filters.get("project_id")
                project_name = filters.get("project_name")
                if project_id is None and project_name is not None:
                    project_id = _resolve_project_name_to_id(
                        session, user_id, project_name
                    )
                tasks = list_tasks_service(
                    session,
                    user_id,
                    column_id=filters.get("column_id"),
                    include_archived=filters.get("include_archived", False),
                    project_id=project_id,
                )
                result = {"tasks": [_task_to_dict(t) for t in tasks]}
                tool_messages.append(
                    ToolMessage(
                        content=json.dumps(result, default=str),
                        tool_call_id=tool_call_id,
                    )
                )
            elif name == "list_projects":
                projects = list_projects_service(session, user_id)
                result = {"projects": [_project_to_dict(p) for p in projects]}
                tool_messages.append(
                    ToolMessage(
                        content=json.dumps(result, default=str),
                        tool_call_id=tool_call_id,
                    )
                )
            elif name == "get_task":
                parsed = get_task_tool.invoke(args)
                task = get_task_service(session, parsed["task_id"], user_id)
                result = {"task": _task_to_dict(task)}
                tool_messages.append(
                    ToolMessage(
                        content=json.dumps(result, default=str),
                        tool_call_id=tool_call_id,
                    )
                )
            else:
                raise ValueError(f"unsupported tool: {name}")

        return {"messages": tool_messages, "proposed_changes": changes}

    def propose_node(state: AgentState, config: RunnableConfig) -> dict:
        diff = ProposedDiff(changes=state.get("proposed_changes", []))
        decision = interrupt({"diff": diff})
        approved = bool(decision.get("approved")) if isinstance(decision, dict) else False
        return {"approved": approved}

    def apply_node(state: AgentState, config: RunnableConfig) -> dict:
        if not state.get("approved"):
            return {
                "applied_results": [],
                "applied_moved_results": [],
                "draft": None,
            }

        user_id = uuid.UUID(config["configurable"]["user_id"])
        session = _session_from_config(config)
        own_session = config.get("configurable", {}).get("session") is None

        try:
            created: list = []
            moved: list = []
            for change in state.get("proposed_changes", []):
                if isinstance(change, CreateTaskChange):
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
                    # Serialize immediately while the SQLAlchemy object is still
                    # fresh; a subsequent service commit can expire it.
                    created.append(_json_safe(task.model_dump()))
                elif isinstance(change, MoveTaskChange):
                    task = move_task_service(
                        session,
                        user_id,
                        change.task_id,
                        change.to_column_id,
                        change.position,
                    )
                    moved.append(_json_safe(task.model_dump()))
                else:
                    raise ValueError(f"unsupported change type: {type(change)}")
            return {
                "applied_results": created,
                "applied_moved_results": moved,
                "draft": None,
            }
        finally:
            if own_session:
                session.close()

    def route_after_agent(state: AgentState) -> str:
        last = state["messages"][-1]
        if _extract_tool_calls(last):
            return "tools"
        return END

    def route_after_tools(state: AgentState) -> str:
        if state.get("proposed_changes"):
            return "propose"
        # If there are only read-tool results, loop back to the agent so it can
        # answer using the fetched data.
        last = state["messages"][-1]
        if isinstance(last, ToolMessage):
            return "agent"
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
    builder.add_conditional_edges("tools", route_after_tools)
    builder.add_conditional_edges("propose", route_after_propose)
    builder.add_edge("apply", END)

    from langgraph.checkpoint.memory import MemorySaver

    return builder.compile(checkpointer=MemorySaver())


# Default graph instance used by the SSE endpoint. The model is resolved lazily
# inside agent_node, so importing this module does not require OPENROUTER_API_KEY.
graph = build_graph(model=None)
