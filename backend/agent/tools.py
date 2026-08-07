"""Agent tools.

Tools are split into two categories:
- Read tools (list_tasks, list_projects, get_task) execute immediately and return
  data to the LLM.
- Mutation tools (create_task, move_task) propose changes; they never mutate the
  database. The apply node in the graph is responsible for persisting approved
  changes.
"""

import uuid

from langchain_core.tools import tool

from models import ChecklistItem, ColumnId, _strip_blank_checklist_items


_VALID_COLUMNS = set(ColumnId.__args__)  # type: ignore[attr-defined]


def create_task(
    title: str,
    column_id: str,
    description: str | None = None,
    project_id: str | uuid.UUID | None = None,
    checklist: list[dict] | None = None,
) -> dict:
    """Propose creating a new task.

    Returns a dict that can be validated into a CreateTaskChange. Raises
    ValueError for invalid arguments so the graph can surface an error event.
    """
    if column_id not in _VALID_COLUMNS:
        raise ValueError(f"invalid column_id: {column_id}")

    cleaned_title = title.strip()
    if not cleaned_title:
        raise ValueError("title cannot be blank")

    parsed_project_id: uuid.UUID | None = None
    if project_id is not None:
        parsed_project_id = (
            project_id if isinstance(project_id, uuid.UUID) else uuid.UUID(project_id)
        )

    items: list[ChecklistItem] = []
    if checklist is not None:
        items = _strip_blank_checklist_items(
            [ChecklistItem(**item) for item in checklist]
        )

    return {
        "type": "create_task",
        "title": cleaned_title,
        "description": description,
        "column_id": column_id,
        "project_id": parsed_project_id,
        "checklist": items,
    }


def move_task(
    task_id: str,
    column_id: str,
    position: int | None = None,
) -> dict:
    """Propose moving an existing task to a different column.

    The caller must supply the task id and target column; the graph's tool_node
    fills the current title and source column from the database before building
    the MoveTaskChange.
    """
    if column_id not in _VALID_COLUMNS:
        raise ValueError(f"invalid column_id: {column_id}")

    parsed_task_id = uuid.UUID(task_id)
    if position is not None and position < 0:
        raise ValueError("position cannot be negative")

    return {
        "type": "move_task",
        "task_id": parsed_task_id,
        "column_id": column_id,
        "position": position,
    }


def list_tasks(
    column_id: str | None = None,
    include_archived: bool = False,
    project_id: str | uuid.UUID | None = None,
    project_name: str | None = None,
) -> dict:
    """List tasks on the board.

    Returns a dict with the requested filters. The graph's tool_node executes
    the actual database query using the current user's session and resolves
    project_name to a project_id when needed.
    """
    if column_id is not None and column_id not in _VALID_COLUMNS:
        raise ValueError(f"invalid column_id: {column_id}")

    parsed_project_id: uuid.UUID | None = None
    if project_id is not None:
        parsed_project_id = (
            project_id if isinstance(project_id, uuid.UUID) else uuid.UUID(project_id)
        )

    return {
        "column_id": column_id,
        "include_archived": include_archived,
        "project_id": parsed_project_id,
        "project_name": project_name.strip() if project_name else None,
    }


def list_projects() -> dict:
    """List projects on the board.

    Returns an empty command dict; the graph's tool_node executes the database
    query using the current user's session.
    """
    return {}


def get_task(task_id: str) -> dict:
    """Get details for a single task.

    Returns a dict with the requested task id. The graph's tool_node executes
    the actual database query using the current user's session.
    """
    return {"task_id": uuid.UUID(task_id)}


# LangChain tool schemas used for LLM binding and invocation.
create_task_tool = tool("create_task", description=create_task.__doc__)(create_task)
move_task_tool = tool("move_task", description=move_task.__doc__)(move_task)
list_tasks_tool = tool("list_tasks", description=list_tasks.__doc__)(list_tasks)
list_projects_tool = tool("list_projects", description=list_projects.__doc__)(list_projects)
get_task_tool = tool("get_task", description=get_task.__doc__)(get_task)
