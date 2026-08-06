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

from agent.graph import _default_model, build_graph

from tests.agent_fakes import FakeToolCallingModel


def make_graph(tool_args):
    model = FakeToolCallingModel(tool_args=tool_args)
    return build_graph(model=model)


class QueueFakeModel(BaseChatModel):
    """A fake LLM that returns queued AIMessages in order."""

    responses: list[AIMessage]

    @property
    def _llm_type(self) -> str:
        return "queue_fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if not self.responses:
            raise RuntimeError("QueueFakeModel ran out of responses")
        message = self.responses.pop(0)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation], llm_output={})

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"responses_left": len(self.responses)}


def _assistant(content: str) -> AIMessage:
    return AIMessage(content=content)


def _tool_call(name: str, args: dict) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"id": "call_1", "name": name, "args": args}],
    )


class TestAgentGraphHitlFlow:
    """End-to-end graph behavior with a deterministic LLM."""

    def test_graph_interrupts_with_proposed_diff(self):
        graph = make_graph({"title": "Wire HITL flow", "column_id": "todo"})

        # The LLM is invoked and returns a create_task tool call.
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
        assert applied[0]["title"] == "Wire HITL flow"
        assert applied[0]["column_id"] == "todo"
        assert applied[0]["user_id"] == str(test_user.id)

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

    def test_agent_node_passes_system_prompt_and_full_history(self):
        """The agent must invoke the LLM with a system prompt and the full
        conversation history, not just the latest user message."""
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
            {
                "messages": [
                    {"role": "user", "content": "Add a task"},
                    {"role": "assistant", "content": "What title?"},
                    {"role": "user", "content": "Test"},
                ]
            },
            config={
                "configurable": {
                    "thread_id": str(uuid.uuid4()),
                    "user_id": str(uuid.uuid4()),
                }
            },
        )

        assert len(recorded_messages) == 4
        assert recorded_messages[0].type == "system"
        assert "focused kanban assistant" in recorded_messages[0].content
        assert any("Add a task" in str(getattr(m, "content", "")) for m in recorded_messages)
        assert any("What title?" in str(getattr(m, "content", "")) for m in recorded_messages)
        assert any("Test" in str(getattr(m, "content", "")) for m in recorded_messages)

    def test_second_turn_llm_receives_full_conversation_history(self):
        """Regression: messages must accumulate across turns via the checkpointer,
        not be replaced. Without the add_messages reducer on AgentState.messages,
        turn 2's LLM would only see the latest user message and forget the title
        it had already confirmed in turn 1.
        """
        recorded_per_call: list[list] = []

        class SequencedRecordingFake(BaseChatModel):
            responses: list[AIMessage]

            @property
            def _llm_type(self) -> str:
                return "sequenced_recording_fake"

            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                recorded_per_call.append(list(messages))
                if not self.responses:
                    raise RuntimeError("SequencedRecordingFake ran out of responses")
                message = self.responses.pop(0)
                generation = ChatGeneration(message=message)
                return ChatResult(generations=[generation], llm_output={})

            async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                raise NotImplementedError

            @property
            def _identifying_params(self) -> dict[str, Any]:
                return {}

        responses = [
            AIMessage(content='Got it, title is "create projects". Which column?'),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "create_task",
                        "args": {"title": "create projects", "column_id": "backlog"},
                    }
                ],
            ),
        ]
        graph = build_graph(model=SequencedRecordingFake(responses=responses))
        thread_id = str(uuid.uuid4())
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": str(uuid.uuid4()),
            }
        }

        graph.invoke(
            {"messages": [{"role": "user", "content": "create a task named create projects"}]},
            config=config,
        )
        result = graph.invoke(
            {"messages": [{"role": "user", "content": "backlog"}]},
            config=config,
        )

        # Turn 2 produced a tool call -> we reached the propose interrupt.
        assert result.get("__interrupt__") is not None

        assert len(recorded_per_call) == 2
        turn2_contents = [
            str(getattr(m, "content", "")) for m in recorded_per_call[1]
        ]
        # Turn 2 must see both the original user message and the assistant's
        # turn-1 confirmation, not just the bare "backlog" reply.
        assert any("create a task named create projects" in c for c in turn2_contents)
        assert any("create projects" in c and "Which column" in c for c in turn2_contents)
        assert any(c == "backlog" for c in turn2_contents)

    def test_read_tool_loops_back_to_agent(self, session, test_user):
        """A read tool (list_tasks) executes immediately and returns a ToolMessage
        so the agent can answer with the fetched data, without requiring approval.
        """
        from services import create_task_service
        from models import TaskCreate

        create_task_service(session, test_user.id, TaskCreate(title="Read docs", column_id="todo"))

        graph = build_graph(
            model=QueueFakeModel(
                responses=[
                    _tool_call("list_tasks", {"column_id": "todo"}),
                    _assistant("You have 1 task in todo: Read docs"),
                ]
            )
        )
        result = graph.invoke(
            {"messages": [{"role": "user", "content": "What do I have in todo?"}]},
            config={
                "configurable": {
                    "thread_id": str(uuid.uuid4()),
                    "user_id": str(test_user.id),
                    "session": session,
                }
            },
        )

        # No interrupt means no approval was requested.
        assert "__interrupt__" not in result or result.get("__interrupt__") is None
        last_message = result["messages"][-1]
        assert "Read docs" in str(getattr(last_message, "content", ""))

    def test_move_task_goes_through_hitl_approval(self, session, test_user):
        """The agent can list tasks, pick one, propose a move, and apply it on approval."""
        from langgraph.types import Command
        from services import create_task_service
        from models import TaskCreate

        task = create_task_service(
            session, test_user.id, TaskCreate(title="Wire HITL", column_id="todo")
        )
        thread_id = str(uuid.uuid4())
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": str(test_user.id),
                "session": session,
            }
        }

        graph = build_graph(
            model=QueueFakeModel(
                responses=[
                    _tool_call("list_tasks", {"column_id": "todo"}),
                    _tool_call("move_task", {"task_id": str(task.id), "column_id": "done"}),
                ]
            )
        )

        # First turn: list tasks, then agent decides to move one.
        result = graph.invoke(
            {"messages": [{"role": "user", "content": "Move the todo task to done"}]},
            config=config,
        )

        interrupt_value = result["__interrupt__"][0].value
        diff = interrupt_value["diff"]
        assert len(diff.changes) == 1
        move_change = diff.changes[0]
        assert move_change.type == "move_task"
        assert move_change.title == "Wire HITL"
        assert move_change.from_column_id == "todo"
        assert move_change.to_column_id == "done"

        # Approve the move.
        final_state = graph.invoke(Command(resume={"approved": True}), config=config)
        moved = final_state["applied_moved_results"]
        assert len(moved) == 1
        assert moved[0]["id"] == str(task.id)
        assert moved[0]["column_id"] == "done"


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

    def test_default_model_binds_all_agent_tools(self):
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

        names = {t.name for t in captured["tools"]}
        assert names == {"create_task", "move_task", "list_tasks", "list_projects", "get_task"}
