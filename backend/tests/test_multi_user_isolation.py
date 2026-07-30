"""Multi-user isolation: every board endpoint is scoped to the authenticated
user. User B must not see or modify user A's tasks, projects, or work blocks,
and daily generation/stats only cover the caller's own data.

The app can only carry one `get_current_user` override at a time, so a single
override dispatches on an `x-test-user` header; the two TestClients below each
send a different value for it.
"""

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

import auth
import db
import main
from models import User


@pytest.fixture()
def clients(session):
    """Two users (A and B) and one TestClient per user."""
    user_a = User(
        email="a@example.com",
        username="usera",
        hashed_password=auth._hash_password("password"),
    )
    user_b = User(
        email="b@example.com",
        username="userb",
        hashed_password=auth._hash_password("password"),
    )
    session.add_all([user_a, user_b])
    session.flush()

    by_header = {"a": user_a, "b": user_b}

    def fake_current_user(request: Request):
        return by_header[request.headers["x-test-user"]]

    main.app.dependency_overrides[db.get_session] = lambda: session
    main.app.dependency_overrides[auth.get_current_user] = fake_current_user
    with (
        TestClient(main.app, headers={"x-test-user": "a"}) as client_a,
        TestClient(main.app, headers={"x-test-user": "b"}) as client_b,
    ):
        yield client_a, client_b
    main.app.dependency_overrides.clear()


def test_task_list_excludes_other_users_tasks(clients):
    client_a, client_b = clients
    created = client_a.post("/tasks", json={"title": "A's task"}).json()

    response = client_b.get("/tasks")
    assert response.status_code == 200
    assert all(t["id"] != created["id"] for t in response.json())


def test_project_list_excludes_other_users_projects(clients):
    client_a, client_b = clients
    created = client_a.post("/projects", json={"name": "A's project"}).json()

    response = client_b.get("/projects")
    assert response.status_code == 200
    assert all(p["id"] != created["id"] for p in response.json())


def test_patch_other_users_task_returns_404(clients):
    client_a, client_b = clients
    task = client_a.post("/tasks", json={"title": "A's task"}).json()

    response = client_b.patch(f"/tasks/{task['id']}", json={"title": "hijacked"})
    assert response.status_code == 404


def test_move_other_users_task_returns_404(clients):
    client_a, client_b = clients
    task = client_a.post("/tasks", json={"title": "A's task"}).json()

    response = client_b.patch(
        f"/tasks/{task['id']}/move",
        json={"column_id": "done", "position": 0},
    )
    assert response.status_code == 404


def test_archive_other_users_task_returns_404(clients):
    client_a, client_b = clients
    task = client_a.post("/tasks", json={"title": "A's task"}).json()

    response = client_b.patch(
        f"/tasks/{task['id']}/archive", json={"archived": True}
    )
    assert response.status_code == 404


def test_delete_other_users_task_returns_404_and_keeps_task(clients):
    client_a, client_b = clients
    task = client_a.post("/tasks", json={"title": "A's task"}).json()

    response = client_b.delete(f"/tasks/{task['id']}")
    assert response.status_code == 404
    assert any(t["id"] == task["id"] for t in client_a.get("/tasks").json())


def test_patch_other_users_project_returns_404(clients):
    client_a, client_b = clients
    project = client_a.post("/projects", json={"name": "A's project"}).json()

    response = client_b.patch(
        f"/projects/{project['id']}", json={"name": "hijacked"}
    )
    assert response.status_code == 404


def test_delete_other_users_project_returns_404_and_keeps_project(clients):
    client_a, client_b = clients
    project = client_a.post("/projects", json={"name": "A's project"}).json()

    response = client_b.delete(f"/projects/{project['id']}")
    assert response.status_code == 404
    assert any(p["id"] == project["id"] for p in client_a.get("/projects").json())


def test_create_task_linked_to_other_users_project_returns_404(clients):
    client_a, client_b = clients
    project = client_a.post("/projects", json={"name": "A's project"}).json()

    response = client_b.post(
        "/tasks", json={"title": "B's task", "project_id": project["id"]}
    )
    assert response.status_code == 404


def test_create_work_block_on_other_users_task_returns_404(clients):
    client_a, client_b = clients
    task = client_a.post("/tasks", json={"title": "A's task"}).json()

    response = client_b.post(
        f"/tasks/{task['id']}/work-blocks", json={"minutes": 25}
    )
    assert response.status_code == 404


def test_list_work_blocks_on_other_users_task_returns_404(clients):
    client_a, client_b = clients
    task = client_a.post("/tasks", json={"title": "A's task"}).json()
    client_a.post(f"/tasks/{task['id']}/work-blocks", json={"minutes": 25})

    response = client_b.get(f"/tasks/{task['id']}/work-blocks")
    assert response.status_code == 404


def test_daily_stats_exclude_other_users_data(clients):
    client_a, client_b = clients
    task = client_a.post("/tasks", json={"title": "A's task"}).json()
    client_a.post(f"/tasks/{task['id']}/work-blocks", json={"minutes": 25})

    response = client_b.get("/work-blocks/stats/daily")
    assert response.status_code == 200
    assert response.json() == []


def test_daily_generation_only_creates_cards_for_own_projects(clients):
    client_a, client_b = clients
    project_a = client_a.post(
        "/projects",
        json={
            "name": "AlphaA",
            "daily_enabled": True,
            "daily_template": {"checklist": ["a"]},
        },
    ).json()
    client_b.post(
        "/projects",
        json={
            "name": "BetaB",
            "daily_enabled": True,
            "daily_template": {"checklist": ["b"]},
        },
    )

    created = client_b.post("/projects/daily-tasks/generate").json()
    assert len(created) == 1
    assert "BetaB" in created[0]["title"]

    # A's project was not touched by B's generation run.
    refreshed_a = next(
        p for p in client_a.get("/projects").json() if p["id"] == project_a["id"]
    )
    assert refreshed_a["daily_last_generated"] is None
