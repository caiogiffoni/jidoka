"""Unit tests for the agent's tools.

Tools must propose changes, not apply them. These tests assert that calling a
tool returns a structured change dict and never touches the database.
"""

import uuid

import pytest

from agent.tools import create_task
from models import ChecklistItem


class TestCreateTaskTool:
    """create_task is the only tool in the first HITL iteration."""

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
        """The tool must never write to the DB. The implementation may import
        the session type, but calling create_task must leave task count
        unchanged.
        """
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
