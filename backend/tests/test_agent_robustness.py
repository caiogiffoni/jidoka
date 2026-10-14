"""Robustness tests for the HITL agent graph and SSE endpoint.

Covers four failure modes:
- a failing tool call is answered with an error ToolMessage, so the thread stays
  usable (no dangling tool_call that would make the LLM API return 400);
- threads are scoped per user on the server, so user B cannot read or resume
  user A's thread by sending the same thread_id;
- apply is all-or-nothing: a failure partway through a diff rolls back the
  changes already applied;
- the Postgres checkpointer persists interrupted threads across graph instances.
"""

import importlib
import uuid
from typing import Any

import psycopg
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from psycopg.rows import dict_row
from sqlmodel import select

import auth
import main
from agent.routes import scoped_thread_id
from models import Task, User
from tests.test_agent_api import _parse_sse

# `agent.graph` the module (the package re-exports the compiled graph as `graph`).
graph_module = importlib.import_module("agent.graph")


class StrictQueueModel(BaseChatModel):
    """Returns queued AIMessages and records every prompt it is sent.

    Like the real LLM API, it refuses a conversation in which an AIMessage's
    tool_call has no matching ToolMessage.
    """

    responses: list[AIMessage]
    calls: list[list] = []

    @property
    def _llm_type(self) -> str:
        return "strict_queue_fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(list(messages))
        answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
        for m in messages:
            for tc in getattr(m, "tool_calls", None) or []:
                if tc["id"] not in answered:
                    raise RuntimeError(f"400: tool_call {tc['id']} has no tool_result")
        if not self.responses:
            raise RuntimeError("StrictQueueModel ran out of responses")
        return ChatResult(
            generations=[ChatGeneration(message=self.responses.pop(0))], llm_output={}
        )

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"responses_left": len(self.responses)}


def _calls(*calls: tuple[str, dict]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"id": f"call_{i}", "name": name, "args": args}
            for i, (name, args) in enumerate(calls, start=1)
        ],
    )


def _config(session, user_id, thread_id=None):
    return {
        "configurable": {
            "thread_id": thread_id or str(uuid.uuid4()),
            "user_id": str(user_id),
            "session": session,
        }
    }


# ---------------------------------------------------------------------------
# 1. Tool errors become error ToolMessages
# ---------------------------------------------------------------------------


class TestToolErrors:
    def test_failed_calls_answer_every_tool_call_and_thread_stays_usable(
        self, session, test_user
    ):
        model = StrictQueueModel(
            responses=[
                _calls(
                    ("get_task", {"task_id": "not-a-uuid"}),
                    ("move_task", {"task_id": str(uuid.uuid4()), "column_id": "done"}),
                    ("delete_everything", {}),
                ),
                AIMessage(content="I couldn't find that task."),
                AIMessage(content="Sure, what next?"),
            ],
            calls=[],
        )
        graph = graph_module.build_graph(model=model)
        config = _config(session, test_user.id)

        result = graph.invoke(
            {"messages": [{"role": "user", "content": "Move my task to done"}]}, config
        )

        # Every call failed: no diff, no interrupt, back to the agent.
        assert "__interrupt__" not in result
        assert result["proposed_changes"] == []
        tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert [m.tool_call_id for m in tool_messages] == ["call_1", "call_2", "call_3"]
        assert all(m.status == "error" for m in tool_messages)
        assert all(m.content.startswith("error: ") for m in tool_messages)
        assert "task not found" in tool_messages[1].content
        assert "unsupported tool: delete_everything" in tool_messages[2].content
        assert result["messages"][-1].content == "I couldn't find that task."

        # A later turn on the same thread still reaches the LLM (no 400).
        result = graph.invoke({"messages": [{"role": "user", "content": "ok"}]}, config)
        assert result["messages"][-1].content == "Sure, what next?"
        assert len(model.calls) == 3

    def test_mixed_batch_proposes_only_the_successful_calls(self, session, test_user):
        model = StrictQueueModel(
            responses=[
                _calls(
                    ("create_task", {"title": "Valid", "column_id": "todo"}),
                    ("move_task", {"task_id": str(uuid.uuid4()), "column_id": "done"}),
                ),
            ],
            calls=[],
        )
        graph = graph_module.build_graph(model=model)

        result = graph.invoke(
            {"messages": [{"role": "user", "content": "do both"}]},
            _config(session, test_user.id),
        )

        changes = result["__interrupt__"][0].value["diff"].changes
        assert [c.title for c in changes] == ["Valid"]
        statuses = {
            m.tool_call_id: m.status
            for m in result["messages"]
            if isinstance(m, ToolMessage)
        }
        assert statuses == {"call_1": "success", "call_2": "error"}


# ---------------------------------------------------------------------------
# 2. Threads are scoped per user
# ---------------------------------------------------------------------------


@pytest.fixture()
def user_b(session):
    user = User(
        email="b@example.com",
        username="userb",
        hashed_password=auth._hash_password("password"),
    )
    session.add(user)
    session.flush()
    return user


@pytest.fixture()
def restore_model():
    original = graph_module.model
    yield
    graph_module.model = original


def _act_as(user):
    main.app.dependency_overrides[auth.get_current_user] = lambda: user


class TestThreadScoping:
    def test_scoped_thread_id_prefixes_user(self):
        user_id = uuid.uuid4()
        assert scoped_thread_id(user_id, "board-1") == f"{user_id}:board-1"

    def test_user_b_cannot_read_or_resume_user_a_thread(
        self, client, session, test_user, user_b, restore_model
    ):
        thread_id = "shared-board-thread"

        # User A gets a pending proposal on the thread.
        graph_module.model = StrictQueueModel(
            responses=[_calls(("create_task", {"title": "A's secret", "column_id": "todo"}))],
            calls=[],
        )
        events = _parse_sse(
            client.post(
                "/agent/stream",
                json={"thread_id": thread_id, "message": "Add A's secret to todo"},
            ).text
        )
        assert any(e["event"] == "interrupt" for e in events)

        # User B resumes the same client thread_id: nothing pending for B.
        _act_as(user_b)
        events = _parse_sse(
            client.post(
                "/agent/stream",
                json={"thread_id": thread_id, "resume": {"approved": True}},
            ).text
        )
        assert [e["event"] for e in events] == ["error", "done"]
        assert "no pending approval" in events[0]["data"]["message"]
        assert session.exec(select(Task).where(Task.title == "A's secret")).first() is None

        # User B messaging on that thread_id sees none of A's history.
        b_model = StrictQueueModel(responses=[AIMessage(content="Hi B")], calls=[])
        graph_module.model = b_model
        client.post("/agent/stream", json={"thread_id": thread_id, "message": "hello"})
        seen = " ".join(str(m.content) for m in b_model.calls[0])
        assert "A's secret" not in seen
        assert "hello" in seen

        # User A can still approve their own proposal.
        _act_as(test_user)
        events = _parse_sse(
            client.post(
                "/agent/stream",
                json={"thread_id": thread_id, "resume": {"approved": True}},
            ).text
        )
        apply = next(e for e in events if e["event"] == "apply")
        assert apply["data"]["created_tasks"][0]["title"] == "A's secret"
        task = session.exec(select(Task).where(Task.title == "A's secret")).one()
        assert task.user_id == test_user.id


# ---------------------------------------------------------------------------
# 3. apply is all-or-nothing
# ---------------------------------------------------------------------------


class TestAtomicApply:
    def test_partial_apply_failure_rolls_back_everything(self, session, test_user):
        existing = Task(
            title="Existing", column_id="todo", position=0, user_id=test_user.id
        )
        session.add(existing)
        session.commit()

        model = StrictQueueModel(
            responses=[
                _calls(
                    ("create_task", {"title": "First", "column_id": "todo"}),
                    ("move_task", {"task_id": str(existing.id), "column_id": "done"}),
                    # Unknown project: proposal succeeds, apply_node 404s.
                    (
                        "create_task",
                        {
                            "title": "Broken",
                            "column_id": "todo",
                            "project_id": str(uuid.uuid4()),
                        },
                    ),
                ),
            ],
            calls=[],
        )
        graph = graph_module.build_graph(model=model)
        config = _config(session, test_user.id)
        result = graph.invoke(
            {"messages": [{"role": "user", "content": "three changes"}]}, config
        )
        assert len(result["__interrupt__"][0].value["diff"].changes) == 3

        with pytest.raises(Exception, match="project not found"):
            graph.invoke(Command(resume={"approved": True}), config)

        titles = {
            t.title
            for t in session.exec(select(Task).where(Task.user_id == test_user.id))
        }
        assert titles == {"Existing"}
        session.refresh(existing)
        assert existing.column_id == "todo"
        assert existing.position == 0

    def test_successful_apply_commits_all_changes(self, session, test_user):
        model = StrictQueueModel(
            responses=[
                _calls(
                    ("create_task", {"title": "One", "column_id": "todo"}),
                    ("create_task", {"title": "Two", "column_id": "todo"}),
                ),
            ],
            calls=[],
        )
        graph = graph_module.build_graph(model=model)
        config = _config(session, test_user.id)
        graph.invoke({"messages": [{"role": "user", "content": "two"}]}, config)

        result = graph.invoke(Command(resume={"approved": True}), config)

        assert [t["title"] for t in result["applied_results"]] == ["One", "Two"]
        tasks = session.exec(
            select(Task).where(Task.user_id == test_user.id).order_by(Task.position)
        ).all()
        assert [(t.title, t.position) for t in tasks] == [("One", 0), ("Two", 1)]


# ---------------------------------------------------------------------------
# 4. Postgres checkpointer
# ---------------------------------------------------------------------------


class TestPostgresCheckpointer:
    def test_conninfo_drops_sqlalchemy_driver(self):
        conninfo = graph_module.checkpointer_conninfo(
            "postgresql+psycopg://jidoka:secret@db:5432/jidoka"
        )
        assert conninfo == "postgresql://jidoka:secret@db:5432/jidoka"

    def test_interrupted_thread_survives_a_new_graph_instance(self, session, test_user):
        from langgraph.checkpoint.postgres import PostgresSaver

        thread_id = f"test-{uuid.uuid4()}"
        with psycopg.connect(
            graph_module.checkpointer_conninfo(),
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
        ) as conn:
            saver = PostgresSaver(conn)
            saver.setup()
            try:
                first = graph_module.build_graph(
                    model=StrictQueueModel(
                        responses=[
                            _calls(("create_task", {"title": "Persisted", "column_id": "todo"}))
                        ],
                        calls=[],
                    ),
                    checkpointer=saver,
                )
                config = _config(session, test_user.id, thread_id)
                first.invoke({"messages": [{"role": "user", "content": "add"}]}, config)

                # A fresh graph (e.g. after a restart) resumes from Postgres.
                second = graph_module.build_graph(
                    model=StrictQueueModel(responses=[], calls=[]),
                    checkpointer=PostgresSaver(conn),
                )
                assert second.get_state(config).next == ("propose",)
                result = second.invoke(Command(resume={"approved": True}), config)
                assert result["applied_results"][0]["title"] == "Persisted"
            finally:
                saver.delete_thread(thread_id)

    def test_init_checkpointer_swaps_shared_graph_onto_postgres(self, monkeypatch):
        from langgraph.checkpoint.postgres import PostgresSaver

        monkeypatch.setenv("AGENT_CHECKPOINTER", "postgres")
        try:
            graph_module.init_checkpointer()
            assert isinstance(graph_module.graph.checkpointer, PostgresSaver)
        finally:
            graph_module.close_checkpointer()
        assert isinstance(graph_module.graph.checkpointer, MemorySaver)

    def test_memory_override_keeps_in_memory_saver(self, monkeypatch):
        monkeypatch.setenv("AGENT_CHECKPOINTER", "memory")
        graph_module.init_checkpointer()
        assert isinstance(graph_module.graph.checkpointer, MemorySaver)
