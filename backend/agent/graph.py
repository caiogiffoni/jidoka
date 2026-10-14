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
from sqlalchemy.engine import make_url


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
from langgraph.checkpoint.memory import MemorySaver
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
    "7. create_task REQUIRES both a title AND a column_id. Do NOT call create_task unless both are explicitly provided.\n"
    "8. If the user gives both required pieces for create_task or move_task, call the tool immediately.\n"
    "9. If one piece is missing, ask only for the missing piece. Do NOT call any tool.\n"
    "   - A standalone column name such as 'backlog', 'todo', 'in_progress', or 'done' means the user wants to create a task in that column; ask for the title.\n"
    "   - A standalone task title without a column means the user wants to create that task; ask for the column and list the valid options.\n"
    "10. If the user corrects you, accept the correction and use the corrected value.\n"
    "11. Stay focused on kanban tasks. Politely decline off-topic questions.\n\n"
    "Examples of correct behavior:\n"
    "- User: 'Create a task Read docs in todo' → create_task(title='Read docs', column_id='todo')\n"
    "- User: 'todo' → 'What title should the new todo task have?' (do not call create_task)\n"
    "- User: Work on my car → 'Which column should I put Work on my car in: backlog, todo, in_progress, or done?' (do not call create_task)\n"
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


def _error_text(exc: Exception) -> str:
    """Short, LLM-readable description of a tool failure."""
    detail = getattr(exc, "detail", None)  # FastAPI HTTPException (e.g. 404)
    text = str(detail if detail is not None else exc).strip()
    return text or type(exc).__name__


def build_graph(model=None, checkpointer=None):
    """Build and compile the HITL agent graph.

    ``checkpointer`` defaults to an in-memory saver, which is what tests use.
    Production swaps in the Postgres checkpointer via ``init_checkpointer()``.
    """
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

        def _run_tool(name, args, tool_call_id):
            """Execute one tool call; return (proposed change or None, ToolMessage)."""
            proposed = ToolMessage(content="proposed", tool_call_id=tool_call_id)
            if name == "create_task":
                result = create_task_tool.invoke(args)
                project_name = _project_name(session, result.get("project_id"))
                return CreateTaskChange(**result, project_name=project_name), proposed
            elif name == "move_task":
                parsed = move_task_tool.invoke(args)
                task = get_task_service(session, parsed["task_id"], user_id)
                change = MoveTaskChange(
                    task_id=task.id,
                    title=task.title,
                    from_column_id=task.column_id,
                    to_column_id=parsed["column_id"],
                    project_name=task.project.name if task.project else None,
                    position=parsed.get("position"),
                )
                return change, proposed
            elif name == "update_task":
                parsed = update_task_tool.invoke(args)
                task = get_task_service(session, parsed["task_id"], user_id)
                project_id = parsed.get("project_id")
                if project_id is None:
                    project_id = task.project_id
                project_name = _project_name(session, project_id)
                change = UpdateTaskChange(
                    task_id=task.id,
                    title=parsed.get("title", task.title),
                    description=parsed.get("description", task.description),
                    project_id=project_id,
                    project_name=project_name,
                    checklist=parsed.get("checklist", task.checklist or []),
                    due_date=parsed.get("due_date", task.due_date),
                )
                return change, proposed
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
                return None, ToolMessage(
                    content=json.dumps(result, default=str),
                    tool_call_id=tool_call_id,
                )
            elif name == "list_projects":
                projects = list_projects_service(session, user_id)
                result = {"projects": [_project_to_dict(p) for p in projects]}
                return None, ToolMessage(
                    content=json.dumps(result, default=str),
                    tool_call_id=tool_call_id,
                )
            elif name == "get_task":
                parsed = get_task_tool.invoke(args)
                task = get_task_service(session, parsed["task_id"], user_id)
                result = {"task": _task_to_dict(task)}
                return None, ToolMessage(
                    content=json.dumps(result, default=str),
                    tool_call_id=tool_call_id,
                )
            else:
                raise ValueError(f"unsupported tool: {name}")

        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args", {})
            tool_call_id = tc.get("id", "call_1")
            # Every tool_call must get a matching ToolMessage, or the next LLM
            # call on this thread is rejected with a 400. So a failing call
            # (bad args, unknown task, unsupported tool) becomes an error
            # ToolMessage the agent can react to instead of raising out of the
            # node, and it never contributes a proposed change.
            try:
                change, message = _run_tool(name, args, tool_call_id)
            except Exception as exc:  # noqa: BLE001 - surfaced to the LLM
                tool_messages.append(
                    ToolMessage(
                        content=f"error: {_error_text(exc)}",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                )
                continue
            if change is not None:
                changes.append(change)
            tool_messages.append(message)

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
                "applied_updated_results": [],
                "draft": None,
            }

        user_id = uuid.UUID(config["configurable"]["user_id"])
        session = _session_from_config(config)
        own_session = config.get("configurable", {}).get("session") is None

        try:
            created: list = []
            moved: list = []
            updated: list = []
            # All-or-nothing: every change runs inside one savepoint and the
            # services only flush (commit=False), so a failure partway through
            # rolls back the changes already made and a retry cannot duplicate
            # them. The single commit happens after the whole diff succeeded.
            with session.begin_nested():
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
                            commit=False,
                        )
                        # Serialize immediately while the SQLAlchemy object is
                        # fresh; the final commit expires it.
                        created.append(_json_safe(task.model_dump()))
                    elif isinstance(change, MoveTaskChange):
                        task = move_task_service(
                            session,
                            user_id,
                            change.task_id,
                            change.to_column_id,
                            change.position,
                            commit=False,
                        )
                        moved.append(_json_safe(task.model_dump()))
                    elif isinstance(change, UpdateTaskChange):
                        task = update_task_service(
                            session,
                            user_id,
                            change.task_id,
                            TaskUpdate(
                                title=change.title,
                                description=change.description,
                                project_id=change.project_id,
                                checklist=change.checklist,
                                due_date=change.due_date,
                            ),
                            commit=False,
                        )
                        updated.append(_json_safe(task.model_dump()))
                    else:
                        raise ValueError(f"unsupported change type: {type(change)}")
            session.commit()
            return {
                "applied_results": created,
                "applied_moved_results": moved,
                "applied_updated_results": updated,
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

    return builder.compile(
        checkpointer=checkpointer if checkpointer is not None else MemorySaver()
    )


# Default graph instance used by the SSE endpoint. The model is resolved lazily
# inside agent_node, so importing this module does not require OPENROUTER_API_KEY.
# It starts on an in-memory checkpointer so importing needs no live DB either;
# the FastAPI lifespan calls init_checkpointer() to move it onto Postgres.
graph = build_graph(model=None)

_checkpoint_pool = None


def checkpointer_conninfo(database_url: str = db.DATABASE_URL) -> str:
    """Convert the SQLAlchemy URL (postgresql+psycopg://...) to a psycopg conninfo."""
    url = make_url(database_url).set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def init_checkpointer() -> None:
    """Persist agent threads in Postgres (LangGraph PostgresSaver).

    Opens a connection pool on DATABASE_URL, creates/migrates the checkpoint
    tables once via ``setup()``, and points the shared ``graph`` at it so
    interrupted HITL threads survive restarts and multiple workers. Setting
    ``AGENT_CHECKPOINTER=memory`` keeps the in-memory saver (the test suite
    does this so checkpoints are not left behind in the dev database).
    """
    global _checkpoint_pool
    if os.environ.get("AGENT_CHECKPOINTER", "postgres").lower() == "memory":
        return
    if _checkpoint_pool is not None:
        return

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        checkpointer_conninfo(),
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )
    try:
        saver = PostgresSaver(pool)
        saver.setup()
    except Exception:
        pool.close()
        raise
    _checkpoint_pool = pool
    graph.checkpointer = saver


def close_checkpointer() -> None:
    """Close the Postgres pool (if any) and fall back to the in-memory saver."""
    global _checkpoint_pool
    if _checkpoint_pool is None:
        return
    graph.checkpointer = MemorySaver()
    _checkpoint_pool.close()
    _checkpoint_pool = None
