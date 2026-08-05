"""Property-based tests for agent invariants.

These tests generate random valid and invalid inputs and assert the spec
invariants hold across the input space.
"""

import uuid

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from langgraph.types import Command

from agent.graph import build_graph
from agent.state import CreateTaskChange
from agent.tools import create_task
from models import ChecklistItem
from tests.agent_fakes import FakeToolCallingModel


VALID_COLUMNS = ["backlog", "todo", "in_progress", "done"]


text_strategy = st.text(alphabet=st.characters(whitelist_categories=("L", "N")), min_size=1, max_size=100)
column_strategy = st.sampled_from(VALID_COLUMNS)


def _make_graph_with_title(title: str, column_id: str, test_user) -> tuple:
    """Build a graph whose fake LLM proposes a single create_task change."""
    model = FakeToolCallingModel(
        tool_args={"title": title, "column_id": column_id}
    )
    graph = build_graph(model=model)
    thread_id = str(uuid.uuid4())
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": str(test_user.id),
        }
    }
    return graph, config


class TestCreateTaskToolProperties:
    """Invariants of the create_task tool function."""

    @given(title=text_strategy, column_id=column_strategy)
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.differing_executors],
    )
    def test_valid_inputs_return_matching_change(self, title, column_id):
        result = create_task(title=title, column_id=column_id)
        assert result["type"] == "create_task"
        assert result["title"] == title.strip()
        assert result["column_id"] == column_id

    @given(title=st.text(min_size=0, max_size=20))
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.differing_executors],
    )
    def test_blank_or_empty_title_is_rejected(self, title):
        if not title.strip():
            with pytest.raises(ValueError):
                create_task(title=title, column_id="todo")

    @given(column_id=st.text(min_size=1))
    @settings(
        max_examples=30,
        suppress_health_check=[HealthCheck.differing_executors],
    )
    def test_non_literal_column_is_rejected(self, column_id):
        if column_id not in VALID_COLUMNS:
            with pytest.raises(ValueError):
                create_task(title="Valid title", column_id=column_id)


class TestApprovedChangeProperties:
    """Invariants of the apply node when approved."""

    @given(title=text_strategy, column_id=column_strategy)
    @settings(
        max_examples=30,
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.differing_executors,
        ],
    )
    def test_approved_change_creates_task_with_matching_fields(self, session, test_user, title, column_id):
        graph, config = _make_graph_with_title(title, column_id, test_user)
        config["configurable"]["session"] = session

        graph.invoke(
            {"messages": [{"role": "user", "content": "add task"}]},
            config=config,
        )

        final_state = graph.invoke(Command(resume={"approved": True}), config=config)
        applied = final_state["applied_results"]
        assert len(applied) == 1
        assert applied[0].title == title.strip()
        assert applied[0].column_id == column_id
        assert applied[0].user_id == test_user.id


class TestRejectedChangeProperties:
    """Invariants of the apply node when rejected."""

    @given(title=text_strategy, column_id=column_strategy)
    @settings(
        max_examples=30,
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.differing_executors,
        ],
    )
    def test_rejected_change_creates_no_task(self, session, test_user, title, column_id):
        from sqlmodel import select

        from models import Task

        graph, config = _make_graph_with_title(title, column_id, test_user)
        config["configurable"]["session"] = session
        before = len(session.exec(select(Task)).all())

        graph.invoke(
            {"messages": [{"role": "user", "content": "add task"}]},
            config=config,
        )

        graph.invoke(Command(resume={"approved": False}), config=config)
        after = len(session.exec(select(Task)).all())
        assert after == before
