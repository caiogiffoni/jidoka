"""Unit tests for the HITL agent graph.

These tests drive the graph with a fake LLM so the suite is deterministic and
does not require an OpenAI API key. They assert the spec-level behavior:
message → tool call → interrupt with diff → resume → apply (or not).
"""

import os
import uuid
from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agent.graph import (
    _clean_title,
    _default_model,
    _detect_column,
    _extract_quoted_title,
    _looks_like_task_request,
    _parse_message,
    _update_draft,
    build_graph,
)

from tests.agent_fakes import FakeToolCallingModel


def make_graph(tool_args):
    model = FakeToolCallingModel(tool_args=tool_args)
    return build_graph(model=model)


class TestAgentGraphHitlFlow:
    """End-to-end graph behavior with a deterministic LLM."""

    def test_graph_interrupts_with_proposed_diff(self):
        graph = make_graph({"title": "Wire HITL flow", "column_id": "todo"})

        # Both title and column are provided, so the agent creates the proposal
        # deterministically without calling the mocked LLM.
        result = graph.invoke(
            {"messages": [{"role": "user", "content": "Add a task 'Wire HITL' to todo"}]},
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
        assert diff.changes[0].title == "Wire HITL"
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

    def test_agent_node_prepends_system_prompt(self):
        """The agent must prepend a system prompt before the user's messages."""
        recorded_messages = []

        class RecordingFake(BaseChatModel):
            tool_args: dict[str, Any]

            @property
            def _llm_type(self) -> str:
                return "recording_fake"

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                recorded_messages.extend(messages)
                tool_call = {"id": "call_1", "name": "create_task", "args": self.tool_args}
                message = AIMessage(content="", tool_calls=[tool_call])
                generation = ChatGeneration(message=message)
                return ChatResult(generations=[generation], llm_output={})

            async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                raise NotImplementedError

            @property
            def _identifying_params(self) -> dict[str, Any]:
                return {"tool_args": self.tool_args}

        graph = build_graph(model=RecordingFake(tool_args={"title": "Test", "column_id": "todo"}))
        graph.invoke(
            {"messages": [{"role": "user", "content": "Add a task"}]},
            config={
                "configurable": {
                    "thread_id": str(uuid.uuid4()),
                    "user_id": str(uuid.uuid4()),
                }
            },
        )

        assert len(recorded_messages) >= 2
        assert recorded_messages[0].type == "system"
        assert "focused kanban assistant" in recorded_messages[0].content
        assert any("Add a task" in str(getattr(m, "content", "")) for m in recorded_messages)


class TestDefaultModel:
    """Coverage for the production LLM factory that mutmut otherwise flags."""

    def test_default_model_uses_configured_openrouter_model(self):
        captured = {}
        bound_model = object()

        def mock_chat(**kwargs):
            captured["kwargs"] = kwargs
            return type("Chat", (), {"bind_tools": lambda self, tools: bound_model})()

        with patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "sk-or-v1-test",
                "OPENROUTER_MODEL": "openai/gpt-4o-sentinel",
            },
            clear=False,
        ):
            with patch("agent.graph.ChatOpenAI", mock_chat):
                result = _default_model()

        assert result is bound_model
        assert captured["kwargs"]["model"] == "openai/gpt-4o-sentinel"
        assert captured["kwargs"]["base_url"] == "https://openrouter.ai/api/v1"
        assert captured["kwargs"]["api_key"] == "sk-or-v1-test"

    def test_default_model_falls_back_to_openrouter_gpt_4o_mini(self):
        captured = {}

        def mock_chat(**kwargs):
            captured["kwargs"] = kwargs
            return type("Chat", (), {"bind_tools": lambda self, tools: "bound"})()

        # Ensure OPENROUTER_MODEL is not set so we exercise the fallback default.
        with patch.dict(os.environ, {"OPENROUTER_MODEL": ""}, clear=False):
            with patch("agent.graph.ChatOpenAI", mock_chat):
                _default_model()

        assert captured["kwargs"]["model"] == "openai/gpt-4o-mini"
        assert captured["kwargs"]["base_url"] == "https://openrouter.ai/api/v1"

    def test_default_model_uses_openrouter_model_env_var(self):
        captured = {}

        def mock_chat(**kwargs):
            captured["kwargs"] = kwargs
            return type("Chat", (), {"bind_tools": lambda self, tools: "bound"})()

        with patch.dict(os.environ, {"OPENROUTER_MODEL": "deepseek/deepseek-chat"}, clear=True):
            with patch("agent.graph.ChatOpenAI", mock_chat):
                _default_model()

        assert captured["kwargs"]["model"] == "deepseek/deepseek-chat"
        assert captured["kwargs"]["base_url"] == "https://openrouter.ai/api/v1"

    def test_default_model_binds_create_task_tool(self):
        captured = {}

        def mock_chat(**kwargs):
            return type(
                "Chat",
                (),
                {"bind_tools": lambda self, tools: captured.setdefault("tools", tools)},
            )()

        with patch.dict(os.environ, {"OPENROUTER_MODEL": ""}, clear=False):
            with patch("agent.graph.ChatOpenAI", mock_chat):
                _default_model()

        assert len(captured["tools"]) == 1
        assert captured["tools"][0].name == "create_task"


class TestDraftExtraction:
    """Unit tests for the rule-based task-draft accumulation."""

    def test_extract_quoted_title(self):
        assert _extract_quoted_title('Create "Work on car"') == "Work on car"
        assert _extract_quoted_title("Create 'Work on car'") == "Work on car"
        assert _extract_quoted_title("Create Work on car") is None

    def test_detect_column(self):
        assert _detect_column("put it in todo") == "todo"
        assert _detect_column("backlog") == "backlog"
        assert _detect_column("in_progress") == "in_progress"
        assert _detect_column("no column here") is None

    def test_update_draft_accumulates_title_then_column(self):
        draft = _update_draft(None, [{"role": "user", "content": "Create 'Work on car'"}])
        assert draft["title"] == "Work on car"
        assert draft.get("column_id") is None

        draft = _update_draft(draft, [{"role": "user", "content": "todo"}])
        assert draft["title"] == "Work on car"
        assert draft["column_id"] == "todo"

    def test_update_draft_does_not_overwrite_title_with_column_reply(self):
        draft = {"title": "Work on car", "column_id": None}
        draft = _update_draft(draft, [{"role": "user", "content": "in_progress"}])
        assert draft["title"] == "Work on car"
        assert draft["column_id"] == "in_progress"

    def test_parse_message_extracts_quoted_title_and_column(self):
        assert _parse_message("Create 'Read docs' in todo") == {
            "title": "Read docs",
            "column_id": "todo",
        }

    def test_parse_message_title_only_asks_for_column_later(self):
        assert _parse_message('can you create "Work on car"?') == {
            "title": "Work on car"
        }

    def test_parse_message_column_only(self):
        assert _parse_message("backlog") == {"column_id": "backlog"}
        assert _parse_message("in_progress") == {"column_id": "in_progress"}

    def test_clean_title_strips_task_filler(self):
        assert _clean_title("Add a task to wire HITL", None) == "wire HITL"
        assert _clean_title("Create a task Read docs in todo", "todo") == "Read docs"
        assert _clean_title("Add a task", None) == ""

    def test_looks_like_task_request(self):
        assert _looks_like_task_request("Create a task")
        assert _looks_like_task_request("Add 'Buy milk'")
        assert _looks_like_task_request("make new task")
        assert _looks_like_task_request("todo")
        assert _looks_like_task_request("in_progress")
        assert not _looks_like_task_request("Who is the president?")
        assert not _looks_like_task_request("Move task 123 to done")
