"""Agent tools.

Tools propose changes; they never mutate the database. The apply node in the
graph is responsible for persisting approved changes.
"""

import uuid

from models import ChecklistItem, ColumnId, _strip_blank_checklist_items


_VALID_COLUMNS = set(ColumnId.__args__)  # type: ignore[attr-defined]


def create_task(
    title: str,
    description: str | None = None,
    column_id: str = "todo",
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
