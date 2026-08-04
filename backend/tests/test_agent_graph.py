"""Unit tests for the HITL agent graph.

These tests drive the graph with a fake LLM so the suite is deterministic and
does not require an OpenAI API key. They assert the spec-level behavior:
message → tool call → interrupt with diff → resume → apply (or not).
"""

import os
import uuid
from unittest.mock import patch

import pytest

from agent.graph import _default_model, build_graph
from tests.agent_fakes import FakeToolCallingModel


def make_graph(tool_args):
    model = FakeToolCallingModel(tool_args=tool_args)
    return build_graph(model=model)


class TestAgentGraphHitlFlow:
    """End-to-end graph behavior with a deterministic LLM."""

    def test_graph_interrupts_with_proposed_diff(self):
        graph = make_graph({"title": "Wire HITL flow", "column_id": "todo"})

        result = graph.invoke(
            {"messages": [{"role": "user", "content": "Add a task to wire HITL"}]},
            config={
                "configurable": {
                    "thread_id": str(uuid.uuid4()),
                    "user_id": str(uuid.uuid4()),
                }
            },
        )

        interrupt_value = result["__interrupt__"][0].value
        diff = interrupt_value["diff"]
        assert len(diff.changes) == 1
        assert diff.changes[0].title == "Wire HITL flow"
        assert diff.changes[0].column_id == "todo"

    def test_approved_create_task_persists_to_db(self, session, test_user):
        graph = make_graph({"title": "Wire HITL flow", "column_id": "todo"})
        thread_id = str(uuid.uuid4())
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": str(test_user.id),
                "session": session,
            }
        }

        graph.invoke(
            {"messages": [{"role": "user", "content": "Add a task"}]},
            config=config,
        )

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
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": str(test_user.id),
                "session": session,
            }
        }

        before = len(session.exec(select(Task)).all())

        graph.invoke(
            {"messages": [{"role": "user", "content": "Add a task"}]},
            config=config,
        )

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
                config={
                    "configurable": {
                        "thread_id": str(uuid.uuid4()),
                        "user_id": str(uuid.uuid4()),
                    }
                },
            )

    def test_graph_rejects_invalid_column_from_tool_args(self):
        graph = make_graph({"title": "Bad column", "column_id": "bogus"})

        with pytest.raises(Exception):
            graph.invoke(
                {"messages": [{"role": "user", "content": "Add a task"}]},
                config={
                    "configurable": {
                        "thread_id": str(uuid.uuid4()),
                        "user_id": str(uuid.uuid4()),
                    }
                },
            )


class TestDefaultModel:
    """Coverage for the production LLM factory that mutmut otherwise flags."""

    def test_default_model_uses_configured_openai_model(self):
        captured = {}
        bound_model = object()

        def mock_chat(**kwargs):
            captured["kwargs"] = kwargs
            return type("Chat", (), {"bind_tools": lambda self, tools: bound_model})()

        with patch.dict(os.environ, {"OPENAI_MODEL": "gpt-4o-sentinel"}, clear=False):
            with patch("agent.graph.ChatOpenAI", mock_chat):
                result = _default_model()

        assert result is bound_model
        assert captured["kwargs"]["model"] == "gpt-4o-sentinel"

    def test_default_model_falls_back_to_gpt_4o_mini(self):
        captured = {}

        def mock_chat(**kwargs):
            captured["kwargs"] = kwargs
            return type("Chat", (), {"bind_tools": lambda self, tools: "bound"})()

        # Ensure OPENAI_MODEL is not set so we exercise the fallback default.
        with patch.dict(os.environ, {"OPENAI_MODEL": ""}, clear=False):
            with patch("agent.graph.ChatOpenAI", mock_chat):
                _default_model()

        assert captured["kwargs"]["model"] == "gpt-4o-mini"

    def test_default_model_uses_openai_model_env_var(self):
        captured = {}

        def mock_chat(**kwargs):
            captured["kwargs"] = kwargs
            return type("Chat", (), {"bind_tools": lambda self, tools: "bound"})()

        with patch.dict(os.environ, {"OPENAI_MODEL": "gpt-4o"}, clear=True):
            with patch("agent.graph.ChatOpenAI", mock_chat):
                _default_model()

        assert captured["kwargs"]["model"] == "gpt-4o"

    def test_default_model_binds_create_task_tool(self):
        captured = {}

        def mock_chat(**kwargs):
            return type(
                "Chat",
                (),
                {"bind_tools": lambda self, tools: captured.setdefault("tools", tools)},
            )()

        with patch.dict(os.environ, {"OPENAI_MODEL": ""}, clear=False):
            with patch("agent.graph.ChatOpenAI", mock_chat):
                _default_model()

        assert len(captured["tools"]) == 1
        assert captured["tools"][0].name == "create_task"
