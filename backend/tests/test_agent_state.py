"""Unit tests for agent state and change schemas.

These tests are spec-first: they verify the shape and validation rules of the
objects that flow through the HITL agent graph, independent of any
implementation detail.
"""

import uuid

import pytest
from pydantic import ValidationError

from agent.state import (
    AgentState,
    AppliedResult,
    CreateTaskChange,
    MoveTaskChange,
    ProposedDiff,
)
from models import ChecklistItem


class TestCreateTaskChange:
    """A CreateTaskChange is the unit of proposed work the agent hands to the
    human for approval."""

    def test_happy_path_defaults_to_todo(self):
        change = CreateTaskChange(title="Wire HITL flow")
        assert change.title == "Wire HITL flow"
        assert change.column_id == "todo"
        assert change.description is None
        assert change.project_id is None
        assert change.checklist == []
        assert change.type == "create_task"

    def test_all_fields_persist(self):
        project_id = uuid.uuid4()
        change = CreateTaskChange(
            title="Wire HITL flow",
            description="End-to-end approval stream",
            column_id="in_progress",
            project_id=project_id,
            checklist=[ChecklistItem(text="build graph", checked=False)],
        )
        assert change.description == "End-to-end approval stream"
        assert change.column_id == "in_progress"
        assert change.project_id == project_id
        assert change.checklist == [ChecklistItem(text="build graph", checked=False)]

    @pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
    def test_blank_title_is_rejected(self, raw):
        with pytest.raises(ValidationError):
            CreateTaskChange(title=raw)

    def test_invalid_column_is_rejected(self):
        with pytest.raises(ValidationError):
            CreateTaskChange(title="Wire HITL flow", column_id="bogus")

    def test_blank_checklist_items_are_stripped(self):
        change = CreateTaskChange(
            title="Wire HITL flow",
            checklist=[
                ChecklistItem(text="build graph", checked=False),
                ChecklistItem(text="   ", checked=False),
                ChecklistItem(text="", checked=False),
                ChecklistItem(text="write tests", checked=True),
            ],
        )
        assert change.checklist == [
            ChecklistItem(text="build graph", checked=False),
            ChecklistItem(text="write tests", checked=True),
        ]

    def test_type_is_literal_create_task(self):
        change = CreateTaskChange(title="Wire HITL flow")
        assert change.model_dump()["type"] == "create_task"


class TestMoveTaskChange:
    """A MoveTaskChange is the unit of proposed task movement."""

    def test_happy_path(self):
        task_id = uuid.uuid4()
        change = MoveTaskChange(
            task_id=task_id,
            title="Wire HITL flow",
            from_column_id="backlog",
            to_column_id="todo",
        )
        assert change.task_id == task_id
        assert change.title == "Wire HITL flow"
        assert change.from_column_id == "backlog"
        assert change.to_column_id == "todo"
        assert change.position is None
        assert change.type == "move_task"

    def test_position_is_optional(self):
        task_id = uuid.uuid4()
        change = MoveTaskChange(
            task_id=task_id,
            title="Wire HITL flow",
            from_column_id="backlog",
            to_column_id="todo",
            position=0,
        )
        assert change.position == 0

    def test_invalid_source_or_target_column_is_rejected(self):
        task_id = uuid.uuid4()
        with pytest.raises(ValidationError):
            MoveTaskChange(
                task_id=task_id,
                title="Wire HITL flow",
                from_column_id="bogus",
                to_column_id="todo",
            )
        with pytest.raises(ValidationError):
            MoveTaskChange(
                task_id=task_id,
                title="Wire HITL flow",
                from_column_id="backlog",
                to_column_id="bogus",
            )

    def test_negative_position_is_rejected(self):
        task_id = uuid.uuid4()
        with pytest.raises(ValidationError):
            MoveTaskChange(
                task_id=task_id,
                title="Wire HITL flow",
                from_column_id="backlog",
                to_column_id="todo",
                position=-1,
            )


class TestProposedDiff:
    """A ProposedDiff wraps one or more changes presented to the user."""

    def test_empty_diff_is_valid(self):
        diff = ProposedDiff(changes=[])
        assert diff.changes == []

    def test_diff_with_multiple_changes(self):
        diff = ProposedDiff(
            changes=[
                CreateTaskChange(title="First task"),
                CreateTaskChange(title="Second task", column_id="backlog"),
            ]
        )
        assert len(diff.changes) == 2
        assert diff.changes[0].title == "First task"
        assert diff.changes[1].column_id == "backlog"

    def test_diff_can_hold_move_changes(self):
        task_id = uuid.uuid4()
        diff = ProposedDiff(
            changes=[
                MoveTaskChange(
                    task_id=task_id,
                    title="Wire HITL flow",
                    from_column_id="backlog",
                    to_column_id="todo",
                )
            ]
        )
        assert len(diff.changes) == 1
        assert diff.changes[0].type == "move_task"


class TestAppliedResult:
    """An AppliedResult records what the apply node actually created or moved."""

    def test_result_can_hold_created_tasks(self):
        result = AppliedResult(created_tasks=[])
        assert result.created_tasks == []

    def test_result_can_hold_moved_tasks(self):
        result = AppliedResult(moved_tasks=[])
        assert result.moved_tasks == []


class TestAgentState:
    """AgentState is the LangGraph state carrier."""

    def test_state_can_carry_expected_keys(self):
        state = AgentState(
            messages=[],
            proposed_changes=[CreateTaskChange(title="Wire HITL flow")],
            approved=None,
            applied_results=[],
            applied_moved_results=[],
        )
        assert state["approved"] is None
        assert len(state["proposed_changes"]) == 1
