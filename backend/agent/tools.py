"""Agent tools. Tools propose changes; they never mutate the database."""

from agent.state import CreateTaskChange


def create_task(
    title: str,
    description: str | None = None,
    column_id: str = "todo",
    project_id: str | None = None,
    checklist: list[dict] | None = None,
) -> dict:
    """Propose creating a new task."""
    raise NotImplementedError("create_task tool not yet implemented")
