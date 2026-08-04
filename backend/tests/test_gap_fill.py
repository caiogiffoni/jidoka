"""Gap-fill tests: full-replace PATCH on projects, work-block 404s, the daily
stats default window, email validation on register, expired JWT rejection, and
daily generation firing again on the next UTC day.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

import db
import main
from routers import projects as projects_router


@pytest.fixture()
def anon_client(session):
    """A client with no authenticated user (but still using the test session)."""
    main.app.dependency_overrides[db.get_session] = lambda: session
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


def test_update_project_omitting_daily_template_wipes_it(client):
    """PATCH /projects/{id} is a full replace: an omitted daily_template is
    cleared, the project-level analog of the task checklist wipe."""
    project = client.post(
        "/projects",
        json={
            "name": "Alpha",
            "daily_enabled": True,
            "daily_template": {"title": "Standup", "checklist": ["Post update"]},
        },
    ).json()

    response = client.patch(
        f"/projects/{project['id']}",
        json={"name": "Alpha", "daily_enabled": False},
    )
    assert response.status_code == 200
    assert response.json()["daily_template"] is None


def test_list_work_blocks_on_missing_task_returns_404(client):
    response = client.get(f"/tasks/{uuid.uuid4()}/work-blocks")
    assert response.status_code == 404


def test_daily_stats_default_window_is_seven_days(client):
    """With days omitted, the window covers the last 7 UTC days: a block from
    8 days ago is excluded, one from today is included."""
    now = datetime.now(timezone.utc)
    old_start = (now - timedelta(days=8)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    old_end = old_start + timedelta(minutes=25)

    task = client.post("/tasks", json={"title": "Task"}).json()
    client.post(
        f"/tasks/{task['id']}/work-blocks",
        json={
            "started_at": old_start.isoformat(),
            "ended_at": old_end.isoformat(),
        },
    )
    client.post(f"/tasks/{task['id']}/work-blocks", json={"minutes": 5})

    response = client.get("/work-blocks/stats/daily")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["date"] == now.date().isoformat()
    assert rows[0]["minutes"] == 5


def test_register_rejects_malformed_email(anon_client):
    response = anon_client.post(
        "/auth/register",
        json={
            "email": "not-an-email",
            "username": "validuser",
            "password": "Password1!",
        },
    )
    assert response.status_code == 422


def test_me_rejects_expired_token(anon_client):
    registered = anon_client.post(
        "/auth/register",
        json={
            "email": "expired@example.com",
            "username": "expireduser",
            "password": "Password1!",
        },
    ).json()
    past = datetime.now(timezone.utc) - timedelta(days=1)
    expired_token = jwt.encode(
        {
            "sub": registered["user"]["id"],
            "email": "expired@example.com",
            "username": "expireduser",
            "iat": past,
            "exp": past,
        },
        os.environ["JWT_SECRET_KEY"],
        algorithm="HS256",
    )

    response = anon_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401


class _FakeDatetime(datetime):
    """datetime subclass with a settable now(), for monkeypatching main."""

    current = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.current


def test_daily_generation_fires_again_on_next_utc_day(client, monkeypatch):
    client.post(
        "/projects",
        json={
            "name": "Alpha",
            "daily_enabled": True,
            "daily_template": {"checklist": ["Post update"]},
        },
    )
    monkeypatch.setattr(projects_router, "datetime", _FakeDatetime)

    _FakeDatetime.current = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    first = client.post("/projects/daily-tasks/generate")
    assert len(first.json()) == 1

    _FakeDatetime.current = datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)
    second = client.post("/projects/daily-tasks/generate")
    assert len(second.json()) == 1

    titles = {first.json()[0]["title"], second.json()[0]["title"]}
    assert titles == {
        "Daily - 01-03-26 - Alpha",
        "Daily - 02-03-26 - Alpha",
    }
