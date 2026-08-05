"""Real LLM tests for the HITL agent.

These tests exercise the agent against the live OpenRouter API. They are
excluded from the default pytest run and must be invoked explicitly via
`make test-llm`.
"""

import json
import os
import uuid

import pytest

PASSWORD = "Password1!"


pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(
        not os.environ.get("OPENROUTER_API_KEY"),
        reason="OPENROUTER_API_KEY not set",
    ),
]


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
            current["data"] = (
                json.loads("".join(current["data"])) if current.get("data") else {}
            )
            events.append(current)
            current = {}
    if current:
        current["data"] = (
            json.loads("".join(current["data"])) if current.get("data") else {}
        )
        events.append(current)
    return events


@pytest.fixture()
def token(anon_client):
    """Register a test user and return a JWT token."""
    response = _register(anon_client, "llm-test@example.com", "llmtestuser")
    assert response.status_code == 201
    return response.json()["token"]


def _post_message(anon_client, token, thread_id, message):
    response = anon_client.post(
        "/agent/stream",
        headers=_auth(token),
        json={"thread_id": thread_id, "message": message},
    )
    assert response.status_code == 200
    return _parse_sse_events(response.text)


def _latest_message_content(events) -> str:
    messages = [e for e in events if e["event"] == "message"]
    return messages[-1]["data"].get("content", "").lower() if messages else ""


def _proposed_changes(events) -> list[dict]:
    interrupt = next((e for e in events if e["event"] == "interrupt"), None)
    return interrupt["data"]["changes"] if interrupt else []


def test_real_llm_title_only_asks_for_column(anon_client, token):
    """A title-only request must ask for the column, not hallucinate one."""
    thread_id = str(uuid.uuid4())
    events = _post_message(
        anon_client, token, thread_id, 'Create a task "Work on my car"'
    )
    content = _latest_message_content(events)
    assert "column" in content
    assert any(col in content for col in ("backlog", "todo", "in_progress", "done"))


def test_real_llm_column_only_asks_for_title(anon_client, token):
    """A column-only request must ask for the title."""
    thread_id = str(uuid.uuid4())
    events = _post_message(anon_client, token, thread_id, "todo")
    content = _latest_message_content(events)
    assert "title" in content


def test_real_llm_title_and_column_proposes_task(anon_client, token):
    """When both title and column are provided, the agent proposes immediately."""
    thread_id = str(uuid.uuid4())
    events = _post_message(
        anon_client, token, thread_id, "Create a task 'Read docs' in todo"
    )
    changes = _proposed_changes(events)
    assert len(changes) == 1
    assert changes[0]["title"] == "Read docs"
    assert changes[0]["column_id"] == "todo"


def test_real_llm_multi_turn_title_then_column(anon_client, token):
    """Title on turn 1, column on turn 2, proposal on turn 2."""
    thread_id = str(uuid.uuid4())
    events1 = _post_message(anon_client, token, thread_id, 'Create "Work on my car"')
    assert "column" in _latest_message_content(events1)

    events2 = _post_message(anon_client, token, thread_id, "in_progress")
    changes = _proposed_changes(events2)
    assert len(changes) == 1
    assert changes[0]["title"] == "Work on my car"
    assert changes[0]["column_id"] == "in_progress"


def test_real_llm_off_topic_is_redirected(anon_client, token):
    """Off-topic questions should be politely redirected to kanban tasks."""
    thread_id = str(uuid.uuid4())
    events = _post_message(
        anon_client, token, thread_id, "Who is the president of Brazil?"
    )
    content = _latest_message_content(events)
    assert "kanban" in content or "task" in content


def test_real_llm_full_hitl_create_and_approve(anon_client, token):
    """Full HITL conversation: propose a task, approve it, verify it exists."""
    thread_id = str(uuid.uuid4())

    # Turn 1: propose the task.
    events1 = _post_message(
        anon_client, token, thread_id, "Create a task 'Write release notes' in todo"
    )
    changes = _proposed_changes(events1)
    assert len(changes) == 1
    assert changes[0]["title"] == "Write release notes"
    assert changes[0]["column_id"] == "todo"

    # Turn 2: approve the diff.
    response = anon_client.post(
        "/agent/stream",
        headers=_auth(token),
        json={"thread_id": thread_id, "resume": {"approved": True}},
    )
    assert response.status_code == 200
    events2 = _parse_sse_events(response.text)
    apply = next((e for e in events2 if e["event"] == "apply"), None)
    assert apply is not None
    created = apply["data"]["created_tasks"]
    assert len(created) == 1
    assert created[0]["title"] == "Write release notes"
    assert created[0]["column_id"] == "todo"

    # Verify the task is visible on the board.
    response = anon_client.get("/tasks", headers=_auth(token))
    assert response.status_code == 200
    tasks = response.json()
    assert any(
        t["title"] == "Write release notes" and t["column_id"] == "todo"
        for t in tasks
    )
