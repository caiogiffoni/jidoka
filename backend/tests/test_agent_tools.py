"""Unit tests for the agent's tools.

Tools must propose changes (for mutations) or return query commands (for reads),
not apply them. These tests assert that calling a tool returns a structured
result and never touches the database.
"""

import uuid

import pytest

from agent.tools import create_task, get_task, list_projects, list_tasks, move_task, update_task
from models import ChecklistItem


class TestCreateTaskTool:
    """create_task proposes a new task."""

    def test_returns_create_task_change(self):
        result = create_task(title="Wire HITL flow", column_id="todo")
        assert result["type"] == "create_task"
        assert result["title"] == "Wire HITL flow"
        assert result["column_id"] == "todo"

    def test_accepts_all_arguments(self):
        project_id = uuid.uuid4()
        result = create_task(
            title="Wire HITL flow",
            description="End-to-end approval stream",
            column_id="in_progress",
            project_id=str(project_id),
            checklist=[{"text": "build graph", "checked": False}],
        )
        assert result["description"] == "End-to-end approval stream"
        assert result["column_id"] == "in_progress"
        assert result["project_id"] == project_id
        assert result["checklist"] == [ChecklistItem(text="build graph", checked=False)]

    def test_default_column_is_todo(self):
        result = create_task(title="Backlog item", column_id="backlog")
        assert result["column_id"] == "backlog"

    def test_invalid_column_is_rejected(self):
        with pytest.raises(ValueError):
            create_task(title="Bad", column_id="invalid_column")

    def test_blank_title_is_rejected(self):
        with pytest.raises(ValueError):
            create_task(title="   ", column_id="todo")

    def test_no_database_side_effect(self, session, test_user):
        """The tool must never write to the DB."""
        from sqlmodel import select

        from models import Task

        before = session.exec(select(Task)).all()
        create_task(title="Phantom task", column_id="todo")
        after = session.exec(select(Task)).all()
        assert before == after

    def test_blank_checklist_items_are_stripped(self):
        result = create_task(
            title="Wire HITL flow",
            column_id="todo",
            checklist=[
                {"text": "build graph", "checked": False},
                {"text": "", "checked": False},
                {"text": "   ", "checked": False},
            ],
        )
        assert result["checklist"] == [ChecklistItem(text="build graph", checked=False)]

    def test_none_description_becomes_none(self):
        result = create_task(title="No description", column_id="todo", description=None)
        assert result["description"] is None


class TestMoveTaskTool:
    """move_task proposes a task movement."""

    def test_returns_move_task_change(self):
        task_id = str(uuid.uuid4())
        result = move_task(task_id=task_id, column_id="todo", position=0)
        assert result["type"] == "move_task"
        assert result["task_id"] == uuid.UUID(task_id)
        assert result["column_id"] == "todo"
        assert result["position"] == 0

    def test_position_is_optional(self):
        task_id = str(uuid.uuid4())
        result = move_task(task_id=task_id, column_id="done")
        assert result["position"] is None

    def test_invalid_column_is_rejected(self):
        with pytest.raises(ValueError):
            move_task(task_id=str(uuid.uuid4()), column_id="invalid")

    def test_negative_position_is_rejected(self):
        with pytest.raises(ValueError):
            move_task(task_id=str(uuid.uuid4()), column_id="todo", position=-1)

    def test_malformed_task_id_is_rejected(self):
        with pytest.raises(ValueError):
            move_task(task_id="not-a-uuid", column_id="todo")


class TestUpdateTaskTool:
    """update_task proposes an edit to an existing task."""

    def test_returns_update_task_change(self):
        task_id = str(uuid.uuid4())
        result = update_task(task_id=task_id, description="Updated description")
        assert result["type"] == "update_task"
        assert result["task_id"] == uuid.UUID(task_id)
        assert result["description"] == "Updated description"
        assert "title" not in result

    def test_accepts_all_arguments(self):
        task_id = str(uuid.uuid4())
        project_id = uuid.uuid4()
        result = update_task(
            task_id=task_id,
            title="New title",
            description="Updated description",
            project_id=str(project_id),
            checklist=[{"text": "build graph", "checked": False}],
            due_date="2026-08-15",
        )
        assert result["title"] == "New title"
        assert result["description"] == "Updated description"
        assert result["project_id"] == project_id
        assert result["checklist"] == [ChecklistItem(text="build graph", checked=False)]
        from datetime import date

        assert result["due_date"] == date(2026, 8, 15)

    def test_no_database_side_effect(self, session, test_user):
        """The tool must never write to the DB."""
        from sqlmodel import select

        from models import Task

        before = session.exec(select(Task)).all()
        update_task(task_id=str(uuid.uuid4()), description="Updated description")
        after = session.exec(select(Task)).all()
        assert before == after

    def test_blank_checklist_items_are_stripped(self):
        task_id = str(uuid.uuid4())
        result = update_task(
            task_id=task_id,
            checklist=[
                {"text": "build graph", "checked": False},
                {"text": "", "checked": False},
                {"text": "   ", "checked": False},
            ],
        )
        assert result["checklist"] == [ChecklistItem(text="build graph", checked=False)]

    def test_malformed_task_id_is_rejected(self):
        with pytest.raises(ValueError):
            update_task(task_id="not-a-uuid", description="Updated description")


class TestListTasksTool:
    """list_tasks returns a query command for the graph's tool_node."""

    def test_returns_filter_dict(self):
        result = list_tasks(column_id="backlog", include_archived=True)
        assert result == {
            "column_id": "backlog",
            "include_archived": True,
            "project_id": None,
            "project_name": None,
        }

    def test_defaults_are_valid(self):
        result = list_tasks()
        assert result == {
            "column_id": None,
            "include_archived": False,
            "project_id": None,
            "project_name": None,
        }

    def test_accepts_project_id_filter(self):
        project_id = uuid.uuid4()
        result = list_tasks(project_id=str(project_id))
        assert result["project_id"] == project_id

    def test_accepts_project_name_filter(self):
        result = list_tasks(project_name="Alpha")
        assert result["project_name"] == "Alpha"

    def test_trims_project_name_filter(self):
        result = list_tasks(project_name="  Alpha  ")
        assert result["project_name"] == "Alpha"

    def test_invalid_column_is_rejected(self):
        with pytest.raises(ValueError):
            list_tasks(column_id="invalid")


class TestListProjectsTool:
    """list_projects returns a query command for the graph's tool_node."""

    def test_returns_empty_command(self):
        assert list_projects() == {}


class TestGetTaskTool:
    """get_task returns a query command for the graph's tool_node."""

    def test_returns_task_id_command(self):
        task_id = str(uuid.uuid4())
        result = get_task(task_id=task_id)
        assert result == {"task_id": uuid.UUID(task_id)}

    def test_malformed_task_id_is_rejected(self):
        with pytest.raises(ValueError):
            get_task(task_id="not-a-uuid")
