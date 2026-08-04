"""End-to-end acceptance flow for the HITL agent.

This scenario exercises the real HTTP surface: register, chat with the agent,
receive a proposed diff, approve it, and verify the task was created. The LLM
is replaced with a deterministic fake so the test needs no OpenAI key.
"""

import json
import uuid
from unittest.mock import patch

import pytest

from tests.agent_fakes import FakeToolCallingModel

PASSWORD = "Password1!"


def _register(client, email, username, password=PASSWORD):
    return client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _parse_sse_events(text: str) -> list[dict]:
    events = []
    current = {}
    for line in text.split("\n"):
        if line.startswith("event:"):
            current["event"] = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current.setdefault("data", []).append(line[len("data:") :].strip())
        elif line == "" and current:
            current["data"] = json.loads("".join(current["data"])) if current.get("data") else {}
            events.append(current)
            current = {}
    if current:
        current["data"] = json.loads("".join(current["data"])) if current.get("data") else {}
        events.append(current)
    return events


@pytest.mark.critical()
def test_agent_create_task_hitl_flow(anon_client):
    """Full API-consumer HITL flow: message → interrupt → approve → task."""
    # Register and get a token
    response = _register(anon_client, "agent@example.com", "agentuser")
    assert response.status_code == 201
    token = response.json()["token"]

    thread_id = str(uuid.uuid4())

    # Patch the LLM so the graph proposes a known task
    with patch("agent.graph.model", FakeToolCallingModel(tool_args={"title": "Wire HITL flow", "column_id": "todo"})):
        response = anon_client.post(
            "/agent/stream",
            headers=_auth(token),
            json={"thread_id": thread_id, "message": "Add a task to wire HITL"},
        )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    interrupt = next((e for e in events if e["event"] == "interrupt"), None)
    assert interrupt is not None
    changes = interrupt["data"]["changes"]
    assert len(changes) == 1
    assert changes[0]["title"] == "Wire HITL flow"
    assert changes[0]["column_id"] == "todo"

    # Approve the diff
    with patch("agent.graph.model", FakeToolCallingModel(tool_args={"title": "Wire HITL flow", "column_id": "todo"})):
        response = anon_client.post(
            "/agent/stream",
            headers=_auth(token),
            json={"thread_id": thread_id, "resume": {"approved": True}},
        )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    apply = next((e for e in events if e["event"] == "apply"), None)
    assert apply is not None
    created = apply["data"]["created_tasks"]
    assert len(created) == 1
    assert created[0]["title"] == "Wire HITL flow"
    assert created[0]["column_id"] == "todo"

    # Verify the task is visible on the board
    response = anon_client.get("/tasks", headers=_auth(token))
    assert response.status_code == 200
    tasks = response.json()
    assert any(t["title"] == "Wire HITL flow" and t["column_id"] == "todo" for t in tasks)


@pytest.mark.critical()
def test_agent_rejected_diff_does_not_create_task(anon_client):
    """Rejecting the proposed diff must leave the board unchanged."""
    response = _register(anon_client, "rejecter@example.com", "rejecter")
    assert response.status_code == 201
    token = response.json()["token"]
    thread_id = str(uuid.uuid4())

    with patch("agent.graph.model", FakeToolCallingModel(tool_args={"title": "Rejected task", "column_id": "todo"})):
        anon_client.post(
            "/agent/stream",
            headers=_auth(token),
            json={"thread_id": thread_id, "message": "Add a task"},
        )

    with patch("agent.graph.model", FakeToolCallingModel(tool_args={"title": "Rejected task", "column_id": "todo"})):
        response = anon_client.post(
            "/agent/stream",
            headers=_auth(token),
            json={"thread_id": thread_id, "resume": {"approved": False}},
        )

    assert response.status_code == 200
    response = anon_client.get("/tasks", headers=_auth(token))
    assert response.status_code == 200
    assert not any(t["title"] == "Rejected task" for t in response.json())


def test_agent_stream_rejects_unauthenticated_request(anon_client):
    response = anon_client.post("/agent/stream", json={"thread_id": str(uuid.uuid4())})
    assert response.status_code == 401
