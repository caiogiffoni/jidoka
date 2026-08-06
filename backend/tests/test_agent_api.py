"""End-to-end agent conversation tests via the HTTP API.

These tests drive POST /agent/stream with a deterministic mocked LLM so we can
inspect exactly how the agent behaves across multiple turns without calling
OpenRouter.
"""

import json
import uuid
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

import importlib

graph_module = importlib.import_module("agent.graph")
from agent.state import CreateTaskChange, MoveTaskChange


def _parse_sse(response_text: str) -> list[dict[str, Any]]:
    """Parse a raw SSE body into event dicts."""
    events = []
    for block in response_text.strip().split("\n\n"):
        event = "message"
        data_text = ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_text += line[5:].strip()
        if data_text:
            try:
                data = json.loads(data_text)
            except json.JSONDecodeError:
                data = data_text
            events.append({"event": event, "data": data})
    return events


class QueueFakeModel(BaseChatModel):
    """A fake LLM that returns queued responses in order."""

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


@pytest.fixture()
def queued_graph(client):
    """Replace the module-level agent model with a queue-based fake.

    The original model is restored after the test.
    """
    original_model = graph_module.model
    yield
    graph_module.model = original_model


def _assistant(content: str) -> AIMessage:
    return AIMessage(content=content)


def _tool_call(name: str, args: dict) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"id": "call_1", "name": name, "args": args}],
    )


def _create_task_tool_call(title: str, column_id: str) -> AIMessage:
    return _tool_call("create_task", {"title": title, "column_id": column_id})


def test_conversation_title_then_column(client, queued_graph):
    """Simulate: user gives title, then column, agent proposes task."""
    thread_id = str(uuid.uuid4())

    # Turn 1: the LLM extracts the title and asks for the column.
    graph_module.model = QueueFakeModel(
        responses=[_assistant('Got it, title is "Work on my car". Which column?')]
    )
    res1 = client.post(
        "/agent/stream",
        json={"thread_id": thread_id, "message": 'can you create a task "Work on my car"?'},
    )
    events1 = _parse_sse(res1.text)
    print("\n--- Turn 1 events ---")
    for ev in events1:
        print(ev)

    assert any(
        ev["event"] == "message" and "Work on my car" in str(ev["data"].get("content", ""))
        for ev in events1
    )

    # Turn 2: the LLM now has the full history and calls create_task.
    graph_module.model = QueueFakeModel(
        responses=[_create_task_tool_call("Work on my car", "in_progress")]
    )
    res2 = client.post(
        "/agent/stream",
        json={"thread_id": thread_id, "message": "in_progress"},
    )
    events2 = _parse_sse(res2.text)
    print("\n--- Turn 2 events ---")
    for ev in events2:
        print(ev)

    interrupt_events = [ev for ev in events2 if ev["event"] == "interrupt"]
    assert len(interrupt_events) == 1
    changes = interrupt_events[0]["data"]["changes"]
    assert len(changes) == 1
    change = CreateTaskChange(**changes[0])
    assert change.title == "Work on my car"
    assert change.column_id == "in_progress"


def test_conversation_title_and_column_in_one_message(client, queued_graph):
    """Simulate: user gives title and column in one message."""
    thread_id = str(uuid.uuid4())

    # The LLM extracts both pieces and calls create_task.
    graph_module.model = QueueFakeModel(
        responses=[_create_task_tool_call("Read docs", "todo")]
    )
    res = client.post(
        "/agent/stream",
        json={"thread_id": thread_id, "message": "Create a task 'Read docs' in todo"},
    )
    events = _parse_sse(res.text)
    print("\n--- One-shot events ---")
    for ev in events:
        print(ev)

    interrupt_events = [ev for ev in events if ev["event"] == "interrupt"]
    assert len(interrupt_events) == 1
    change = CreateTaskChange(**interrupt_events[0]["data"]["changes"][0])
    assert change.title == "Read docs"
    assert change.column_id == "todo"


def test_conversation_continues_with_llm_on_second_turn(client, queued_graph):
    """A multi-turn conversation reaches the propose node via the LLM each turn.

    There is no deterministic short-circuit anymore, so the second turn must
    also be handled by the mocked LLM.
    """
    thread_id = str(uuid.uuid4())

    # Turn 1: the LLM asks for the column.
    graph_module.model = QueueFakeModel(
        responses=[_assistant('Got it, title is "Task 852". Which column?')]
    )
    res1 = client.post(
        "/agent/stream",
        json={"thread_id": thread_id, "message": "can you create title = 'Task 852'."},
    )
    events1 = _parse_sse(res1.text)
    print("\n--- Multi-turn turn 1 events ---")
    for ev in events1:
        print(ev)

    # Turn 2: the LLM is invoked again, this time calling create_task.
    graph_module.model = QueueFakeModel(
        responses=[_create_task_tool_call("Task 852", "backlog")]
    )
    res2 = client.post(
        "/agent/stream",
        json={"thread_id": thread_id, "message": "backlog"},
    )
    events2 = _parse_sse(res2.text)
    print("\n--- Multi-turn turn 2 events ---")
    for ev in events2:
        print(ev)

    interrupt_events = [ev for ev in events2 if ev["event"] == "interrupt"]
    assert len(interrupt_events) == 1
    change = CreateTaskChange(**interrupt_events[0]["data"]["changes"][0])
    assert change.title == "Task 852"
    assert change.column_id == "backlog"


def test_conversation_lists_tasks_then_proposes_move(client, queued_graph):
    """The agent reads the board, then proposes moving an existing task."""
    # Seed a task manually so the agent has something to move.
    task_res = client.post(
        "/tasks",
        json={"title": "Wire HITL", "column_id": "todo"},
    )
    assert task_res.status_code == 201
    task = task_res.json()

    thread_id = str(uuid.uuid4())

    # Turn 1: agent lists tasks in todo.
    graph_module.model = QueueFakeModel(
        responses=[_tool_call("list_tasks", {"column_id": "todo"})]
    )
    res1 = client.post(
        "/agent/stream",
        json={"thread_id": thread_id, "message": "What's in todo?"},
    )
    events1 = _parse_sse(res1.text)
    print("\n--- List turn events ---")
    for ev in events1:
        print(ev)

    # No approval requested for a read.
    assert not any(ev["event"] == "interrupt" for ev in events1)

    # Turn 2: agent proposes moving the listed task to done.
    graph_module.model = QueueFakeModel(
        responses=[_tool_call("move_task", {"task_id": task["id"], "column_id": "done"})]
    )
    res2 = client.post(
        "/agent/stream",
        json={"thread_id": thread_id, "message": "Move that task to done"},
    )
    events2 = _parse_sse(res2.text)
    print("\n--- Move turn events ---")
    for ev in events2:
        print(ev)

    interrupt_events = [ev for ev in events2 if ev["event"] == "interrupt"]
    assert len(interrupt_events) == 1
    change = MoveTaskChange(**interrupt_events[0]["data"]["changes"][0])
    assert change.title == "Wire HITL"
    assert change.from_column_id == "todo"
    assert change.to_column_id == "done"


def test_approved_multi_move_emits_all_titles(client, queued_graph):
    """Moving several tasks in one diff surfaces every title in the apply event."""
    titles = ["Alpha", "Beta", "Gamma"]
    task_ids = []
    for title in titles:
        res = client.post("/tasks", json={"title": title, "column_id": "todo"})
        assert res.status_code == 201
        task_ids.append(res.json()["id"])

    thread_id = str(uuid.uuid4())

    # The current move_task tool only moves one task per call, so the LLM would
    # need three separate tool calls for a real multi-move. We simulate that by
    # having the fake LLM return three move_task calls in one AIMessage.
    graph_module.model = QueueFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "c1", "name": "move_task", "args": {"task_id": task_ids[0], "column_id": "done"}},
                    {"id": "c2", "name": "move_task", "args": {"task_id": task_ids[1], "column_id": "done"}},
                    {"id": "c3", "name": "move_task", "args": {"task_id": task_ids[2], "column_id": "done"}},
                ],
            )
        ]
    )
    res1 = client.post(
        "/agent/stream",
        json={"thread_id": thread_id, "message": "move all tasks to done"},
    )
    events1 = _parse_sse(res1.text)

    interrupt_events = [ev for ev in events1 if ev["event"] == "interrupt"]
    assert len(interrupt_events) == 1
    assert len(interrupt_events[0]["data"]["changes"]) == 3
    assert {c["title"] for c in interrupt_events[0]["data"]["changes"]} == set(titles)

    graph_module.model = QueueFakeModel(responses=[])
    res2 = client.post(
        "/agent/stream",
        json={"thread_id": thread_id, "resume": {"approved": True}},
    )
    events2 = _parse_sse(res2.text)

    apply_events = [ev for ev in events2 if ev["event"] == "apply"]
    assert len(apply_events) == 1
    moved = apply_events[0]["data"]["moved_tasks"]
    assert {t["title"] for t in moved} == set(titles)
