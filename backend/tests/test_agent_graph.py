"""Unit tests for the HITL agent graph.

These tests drive the graph with a fake LLM so the suite is deterministic and
does not require an OpenAI API key. They assert the spec-level behavior:
message → tool call → interrupt with diff → resume → apply (or not).
"""

import uuid

import pytest
from langgraph.errors import GraphInterrupt

from agent.graph import build_graph
from tests.agent_fakes import FakeToolCallingModel


def make_graph(tool_args):
    model = FakeToolCallingModel(tool_args=tool_args)
    return build_graph(model=model)


class TestAgentGraphHitlFlow:
    """End-to-end graph behavior with a deterministic LLM."""

    def test_graph_interrupts_with_proposed_diff(self):
        graph = make_graph({"title": "Wire HITL flow", "column_id": "todo"})

        with pytest.raises(GraphInterrupt) as exc_info:
            graph.invoke(
                {"messages": [{"role": "user", "content": "Add a task to wire HITL"}]},
                config={"configurable": {"thread_id": str(uuid.uuid4())}},
            )

        interrupt_value = exc_info.value.args[0]
        diff = interrupt_value["diff"]
        assert len(diff.changes) == 1
        assert diff.changes[0].title == "Wire HITL flow"
        assert diff.changes[0].column_id == "todo"

    def test_approved_create_task_persists_to_db(self, session, test_user):
        graph = make_graph({"title": "Wire HITL flow", "column_id": "todo"})
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        try:
            graph.invoke(
                {"messages": [{"role": "user", "content": "Add a task"}]},
                config=config,
            )
        except GraphInterrupt:
            pass

        from langgraph.types import Command

        final_state = graph.invoke(
            Command(resume={"approved": True}),
            config=config,
        )

        applied = final_state["applied_results"]
        assert len(applied) == 1
        assert applied[0].title == "Wire HITL flow"
        assert applied[0].column_id == "todo"
        assert applied[0].user_id == test_user.id

    def test_rejected_create_task_leaves_db_unchanged(self, session, test_user):
        from sqlmodel import select

        from models import Task

        graph = make_graph({"title": "Wire HITL flow", "column_id": "todo"})
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        before = len(session.exec(select(Task)).all())

        try:
            graph.invoke(
                {"messages": [{"role": "user", "content": "Add a task"}]},
                config=config,
            )
        except GraphInterrupt:
            pass

        from langgraph.types import Command

        graph.invoke(Command(resume={"approved": False}), config=config)

        after = len(session.exec(select(Task)).all())
        assert after == before

    def test_graph_strips_blank_title_from_tool_args(self):
        """If the LLM returns a blank title, the tool node must reject it and
        the graph should surface an error rather than propose an invalid change.
        """
        graph = make_graph({"title": "   ", "column_id": "todo"})

        with pytest.raises(Exception):
            graph.invoke(
                {"messages": [{"role": "user", "content": "Add a task"}]},
                config={"configurable": {"thread_id": str(uuid.uuid4())}},
            )

    def test_graph_rejects_invalid_column_from_tool_args(self):
        graph = make_graph({"title": "Bad column", "column_id": "bogus"})

        with pytest.raises(Exception):
            graph.invoke(
                {"messages": [{"role": "user", "content": "Add a task"}]},
                config={"configurable": {"thread_id": str(uuid.uuid4())}},
            )
