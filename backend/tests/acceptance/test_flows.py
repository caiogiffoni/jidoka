"""End-to-end acceptance flows from an API consumer's perspective.

Each test is an independently runnable scenario that chains real HTTP calls
through FastAPI's TestClient, the way an httpx/curl client would experience
the API. Fixtures (session / test_user / client) come from tests/conftest.py;
anon_client (real tokens, no auth override) is defined locally.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from models import WorkBlock

PASSWORD = "Password1!"


def _register(client, email, username, password=PASSWORD):
    return client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.critical()
def test_auth_lifecycle(anon_client):
    """register → me → login → me again, with real tokens; duplicates and bad
    credentials are rejected; a second user cannot see the first user's data."""
    # register
    response = _register(anon_client, "alice@example.com", "alice")
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["username"] == "alice"
    assert data["user"]["id"]
    token = data["token"]
    assert token

    # me with the registration token
    response = anon_client.get("/auth/me", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"

    # login, then me again with the login token
    response = anon_client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    login_token = response.json()["token"]
    response = anon_client.get("/auth/me", headers=_auth(login_token))
    assert response.status_code == 200
    assert response.json()["username"] == "alice"

    # invalid credentials
    response = anon_client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "WrongPass1!"},
    )
    assert response.status_code == 401
    response = anon_client.post(
        "/auth/login", json={"email": "ghost@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401

    # duplicates
    response = _register(anon_client, "alice@example.com", "otheruser")
    assert response.status_code == 409
    response = _register(anon_client, "other@example.com", "alice")
    assert response.status_code == 409

    # cross-user isolation with real tokens
    task = anon_client.post(
        "/tasks", json={"title": "alice secret"}, headers=_auth(token)
    )
    assert task.status_code == 201
    bob = _register(anon_client, "bob@example.com", "bob").json()
    bob_headers = _auth(bob["token"])
    response = anon_client.get("/tasks", headers=bob_headers)
    assert response.status_code == 200
    assert response.json() == []
    task_id = task.json()["id"]
    response = anon_client.patch(
        f"/tasks/{task_id}",
        json={"title": "hijack"},
        headers=bob_headers,
    )
    assert response.status_code == 404


@pytest.mark.critical()
def test_card_lifecycle_end_to_end(client, session):
    """create → full-replace edit → move across columns → archive → unarchive
    → delete, with positions staying dense at every step."""
    # create three cards in backlog
    ids = []
    for title in ("card A", "card B", "card C"):
        response = client.post(
            "/tasks", json={"title": title, "column_id": "backlog"}
        )
        assert response.status_code == 201
        ids.append(response.json()["id"])

    def backlog_positions():
        tasks = client.get("/tasks").json()
        return [t["position"] for t in tasks if t["column_id"] == "backlog"]

    assert backlog_positions() == [0, 1, 2]

    # full-replace PATCH edit
    response = client.patch(
        f"/tasks/{ids[0]}",
        json={
            "title": "card A (edited)",
            "description": "new description",
            "project_id": None,
            "checklist": [{"text": "step 1", "checked": True}],
            "due_date": "2030-01-15",
        },
    )
    assert response.status_code == 200
    edited = response.json()
    assert edited["title"] == "card A (edited)"
    assert edited["description"] == "new description"
    assert edited["checklist"] == [{"text": "step 1", "checked": True}]
    assert edited["due_date"] == "2030-01-15"

    # move card A from backlog to done
    response = client.patch(
        f"/tasks/{ids[0]}/move", json={"column_id": "done", "position": 0}
    )
    assert response.status_code == 200
    assert response.json()["column_id"] == "done"
    assert response.json()["position"] == 0
    # source column stays dense
    assert backlog_positions() == [0, 1]

    # archive card B: hidden from the default list, positions re-packed
    response = client.patch(f"/tasks/{ids[1]}/archive", json={"archived": True})
    assert response.status_code == 200
    assert response.json()["archived"] is True
    visible = client.get("/tasks").json()
    assert ids[1] not in {t["id"] for t in visible}
    assert backlog_positions() == [0]

    # unarchive card B: re-appended at the end of its column
    response = client.patch(f"/tasks/{ids[1]}/archive", json={"archived": False})
    assert response.status_code == 200
    restored = response.json()
    assert restored["archived"] is False
    assert restored["column_id"] == "backlog"
    assert restored["position"] == 1
    assert backlog_positions() == [0, 1]

    # delete card C: 204 and its work blocks cascade-deleted
    response = client.post(
        f"/tasks/{ids[2]}/work-blocks", json={"minutes": 30}
    )
    assert response.status_code == 201
    block_id = uuid.UUID(response.json()["id"])
    response = client.delete(f"/tasks/{ids[2]}")
    assert response.status_code == 204
    assert client.get(f"/tasks/{ids[2]}/work-blocks").status_code == 404
    assert session.get(WorkBlock, block_id) is None


@pytest.mark.critical()
def test_daily_task_generation_flow(client):
    """daily-enabled project with template → generate → card in todo with the
    spec'd title/description/checklist → second call same UTC day returns []."""
    response = client.post(
        "/projects",
        json={
            "name": "Spanish",
            "daily_enabled": True,
            "daily_template": {
                "title": "Anki review",
                "description": "Clear the review queue",
                "checklist": ["due cards", "new cards"],
            },
        },
    )
    assert response.status_code == 201
    project = response.json()

    response = client.post("/projects/daily-tasks/generate")
    assert response.status_code == 201
    created = response.json()
    assert len(created) == 1
    task = created[0]

    today = datetime.now(timezone.utc).date()
    assert task["title"] == f"Daily - {today:%d-%m-%y} - Spanish - Anki review"
    assert task["column_id"] == "todo"
    assert task["description"] == "Clear the review queue"
    assert task["checklist"] == [
        {"text": "due cards", "checked": False},
        {"text": "new cards", "checked": False},
    ]
    assert task["project_id"] == project["id"]

    # idempotent per UTC day
    response = client.post("/projects/daily-tasks/generate")
    assert response.status_code == 201
    assert response.json() == []


@pytest.mark.standard()
def test_project_time_rollup_then_project_delete(client):
    """project + linked task + timed & manual work blocks roll up into daily
    stats; deleting the project unlinks the task and its time moves to the
    null-project bucket."""
    project = client.post("/projects", json={"name": "Deep Work"}).json()
    task = client.post(
        "/tasks",
        json={"title": "focus session", "project_id": project["id"]},
    ).json()

    # timed block: 25 minutes derived from timestamps
    ended = datetime.now(timezone.utc)
    started = ended - timedelta(minutes=25)
    response = client.post(
        f"/tasks/{task['id']}/work-blocks",
        json={"started_at": started.isoformat(), "ended_at": ended.isoformat()},
    )
    assert response.status_code == 201
    assert response.json()["minutes"] == 25

    # manual block: minutes only
    response = client.post(
        f"/tasks/{task['id']}/work-blocks", json={"minutes": 40}
    )
    assert response.status_code == 201

    # rollup shows 65 minutes under the project
    stats = client.get("/work-blocks/stats/daily").json()
    project_minutes = sum(
        row["minutes"] for row in stats if row["project_id"] == project["id"]
    )
    assert project_minutes == 65
    row = next(r for r in stats if r["project_id"] == project["id"])
    assert row["project_name"] == "Deep Work"

    # delete the project: task survives, unlinked
    assert client.delete(f"/projects/{project['id']}").status_code == 204
    tasks = client.get("/tasks").json()
    surviving = next(t for t in tasks if t["id"] == task["id"])
    assert surviving["project_id"] is None

    # the logged time is still counted, now under the null-project bucket
    stats = client.get("/work-blocks/stats/daily").json()
    assert all(row["project_id"] != project["id"] for row in stats)
    null_minutes = sum(
        row["minutes"] for row in stats if row["project_id"] is None
    )
    assert null_minutes == 65


@pytest.mark.standard()
def test_unauthenticated_requests_are_rejected(anon_client):
    """Board endpoints without a Bearer token must answer 401 or 403."""
    task_id = uuid.uuid4()
    project_id = uuid.uuid4()
    cases = [
        ("GET", "/tasks", None),
        ("POST", "/tasks", {"title": "x"}),
        ("PATCH", f"/tasks/{task_id}", {"title": "x"}),
        ("PATCH", f"/tasks/{task_id}/move", {"column_id": "todo", "position": 0}),
        ("PATCH", f"/tasks/{task_id}/archive", {"archived": True}),
        ("DELETE", f"/tasks/{task_id}", None),
        ("GET", "/projects", None),
        ("POST", "/projects", {"name": "x"}),
        ("POST", "/projects/daily-tasks/generate", None),
        ("GET", "/work-blocks/stats/daily", None),
        ("GET", f"/tasks/{task_id}/work-blocks", None),
        ("POST", f"/tasks/{task_id}/work-blocks", {"minutes": 5}),
        ("GET", "/auth/me", None),
    ]
    for method, path, payload in cases:
        response = anon_client.request(method, path, json=payload)
        assert response.status_code in (401, 403), (
            f"{method} {path} returned {response.status_code}"
        )


@pytest.mark.edge()
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", "/tasks", {"title": "x", "column_id": "bogus"}),
        ("POST", "/tasks", {"column_id": "todo"}),  # missing title
        ("PATCH", "/tasks/{task}/move", {"column_id": "done", "position": -1}),
        ("PATCH", "/tasks/{task}/move", {"column_id": "bogus", "position": 0}),
        ("POST", "/tasks/{task}/work-blocks", {}),  # neither timestamps nor minutes
        ("POST", "/tasks/{task}/work-blocks", {"minutes": 0}),
        ("POST", "/projects", {"daily_enabled": True}),  # missing template
    ],
)
def test_validation_rejections(client, method, path, payload):
    """Malformed payloads must be rejected with 422 before touching state."""
    task = client.post("/tasks", json={"title": "victim"}).json()
    response = client.request(method, path.format(task=task["id"]), json=payload)
    assert response.status_code == 422


@pytest.mark.edge()
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/tasks/{missing}/work-blocks", None),
        ("POST", "/tasks/{missing}/work-blocks", {"minutes": 5}),
        ("PATCH", "/tasks/{missing}", {"title": "x"}),
        ("PATCH", "/tasks/{missing}/move", {"column_id": "todo", "position": 0}),
        ("PATCH", "/tasks/{missing}/archive", {"archived": True}),
        ("DELETE", "/tasks/{missing}", None),
        ("PATCH", "/projects/{missing}", {"name": "x"}),
        ("DELETE", "/projects/{missing}", None),
    ],
)
def test_missing_resources_return_404(client, method, path, payload):
    response = client.request(
        method, path.format(missing=uuid.uuid4()), json=payload
    )
    assert response.status_code == 404


@pytest.mark.edge()
def test_archived_tasks_hidden_by_default_and_restorable(client):
    """Archived tasks are excluded without ?include_archived=true, and
    unarchiving re-appends the card at the end of its column."""
    ids = [
        client.post("/tasks", json={"title": t, "column_id": "todo"}).json()["id"]
        for t in ("one", "two", "three")
    ]

    client.patch(f"/tasks/{ids[1]}/archive", json={"archived": True})

    default_list = client.get("/tasks").json()
    assert [t["id"] for t in default_list] == [ids[0], ids[2]]
    assert [t["position"] for t in default_list] == [0, 1]

    everything = client.get("/tasks", params={"include_archived": "true"}).json()
    assert {t["id"] for t in everything} == set(ids)
    archived = next(t for t in everything if t["id"] == ids[1])
    assert archived["archived"] is True

    restored = client.patch(
        f"/tasks/{ids[1]}/archive", json={"archived": False}
    ).json()
    assert restored["position"] == 2
    default_list = client.get("/tasks").json()
    # unarchiving re-appends at the column end: one, three, two
    assert [t["id"] for t in default_list] == [ids[0], ids[2], ids[1]]
