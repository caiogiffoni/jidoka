"""Unit tests for the agent SSE endpoint.

These tests verify that /agent/stream is authenticated, returns valid SSE
events, and translates graph interrupts/resumes into the protocol the frontend
expects.
"""

import json
import uuid
from unittest.mock import patch

import pytest

from agent.state import CreateTaskChange, ProposedDiff
from models import Task


@pytest.fixture
def auth_client(client, test_user):
    """Authenticated test client with a valid token header."""
    from auth import _create_token

    token = _create_token(test_user)
    client.headers = {"Authorization": f"Bearer {token}"}
    client.user = test_user
    return client


class TestAgentStreamAuth:
    def test_stream_requires_auth(self, client):
        response = client.post("/agent/stream", json={"thread_id": str(uuid.uuid4())})
        assert response.status_code == 401

    def test_stream_accepts_valid_auth(self, auth_client):
        with patch("agent.routes.graph") as mock_graph:
            mock_graph.astream.return_value = iter([])
            response = auth_client.post(
                "/agent/stream",
                json={"thread_id": str(uuid.uuid4()), "message": "hi"},
            )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")


class TestAgentStreamEvents:
    def test_stream_emits_interrupt_event(self, auth_client):
        diff = ProposedDiff(changes=[CreateTaskChange(title="Wire HITL flow")])

        def fake_stream(*args, **kwargs):
            yield {"event": "interrupt", "data": diff.model_dump()}
            yield {"event": "done", "data": "{}"}

        with patch("agent.routes.graph") as mock_graph:
            mock_graph.astream.return_value = fake_stream()
            response = auth_client.post(
                "/agent/stream",
                json={"thread_id": str(uuid.uuid4()), "message": "Add a task"},
            )

        lines = response.text.strip().split("\n\n")
        events = [parse_sse(line) for line in lines if line.startswith("event:")]
        assert any(e["event"] == "interrupt" for e in events)
        interrupt = next(e for e in events if e["event"] == "interrupt")
        assert interrupt["data"]["changes"][0]["title"] == "Wire HITL flow"

    def test_stream_emits_apply_event_after_approval(self, auth_client):
        task = Task(
            title="Wire HITL flow",
            column_id="todo",
            position=0,
            user_id=auth_client.user.id,
        )

        def fake_stream(*args, **kwargs):
            yield {"event": "apply", "data": {"created_tasks": [task.model_dump()]}}
            yield {"event": "done", "data": "{}"}

        with patch("agent.routes.graph") as mock_graph:
            mock_graph.astream.return_value = fake_stream()
            response = auth_client.post(
                "/agent/stream",
                json={
                    "thread_id": str(uuid.uuid4()),
                    "resume": {"approved": True},
                },
            )

        lines = response.text.strip().split("\n\n")
        events = [parse_sse(line) for line in lines if line.startswith("event:")]
        apply = next(e for e in events if e["event"] == "apply")
        assert apply["data"]["created_tasks"][0]["title"] == "Wire HITL flow"

    def test_stream_emits_error_on_exception(self, auth_client):
        def fake_stream(*args, **kwargs):
            raise RuntimeError("LLM exploded")

        with patch("agent.routes.graph") as mock_graph:
            mock_graph.astream.return_value = fake_stream()
            response = auth_client.post(
                "/agent/stream",
                json={"thread_id": str(uuid.uuid4()), "message": "Add a task"},
            )

        assert response.status_code == 200
        lines = response.text.strip().split("\n\n")
        events = [parse_sse(line) for line in lines if line.startswith("event:")]
        assert any(e["event"] == "error" for e in events)


def parse_sse(raw: str) -> dict:
    """Parse one SSE event block into {event, data}."""
    event = None
    data_lines = []
    for line in raw.split("\n"):
        if line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
    data = json.loads("".join(data_lines)) if data_lines else {}
    return {"event": event, "data": data}
