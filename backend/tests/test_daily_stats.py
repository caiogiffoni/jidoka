from datetime import datetime, timedelta, timezone


def test_b26_daily_stats_empty_by_default(client):
    """TESTING.md B26: no work blocks logged in the window -> []."""
    response = client.get("/work-blocks/stats/daily", params={"days": 7})
    assert response.status_code == 200
    assert response.json() == []


def test_b27_daily_stats_aggregates_by_day_and_project(client):
    """TESTING.md B27: one row per (date, project) with time logged."""
    now = datetime.now(timezone.utc)
    yesterday_start = (now - timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    yesterday_end = yesterday_start + timedelta(minutes=25)

    project = client.post("/projects", json={"name": "Alpha"}).json()
    linked_task = client.post(
        "/tasks", json={"title": "Linked", "project_id": project["id"]}
    ).json()
    unlinked_task = client.post("/tasks", json={"title": "Unlinked"}).json()

    # timed block yesterday, on the project-linked task
    client.post(
        f"/tasks/{linked_task['id']}/work-blocks",
        json={
            "started_at": yesterday_start.isoformat(),
            "ended_at": yesterday_end.isoformat(),
        },
    )
    # manual block today, on the same project-linked task
    client.post(f"/tasks/{linked_task['id']}/work-blocks", json={"minutes": 15})
    # manual block today, on a task with no project
    client.post(f"/tasks/{unlinked_task['id']}/work-blocks", json={"minutes": 10})

    response = client.get("/work-blocks/stats/daily", params={"days": 7})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 3

    by_key = {(r["date"], r["project_id"]): r for r in rows}
    today_str = now.date().isoformat()
    yesterday_str = (now - timedelta(days=1)).date().isoformat()

    assert by_key[(yesterday_str, project["id"])]["minutes"] == 25
    assert by_key[(today_str, project["id"])]["minutes"] == 15

    no_project_row = by_key[(today_str, None)]
    assert no_project_row["project_name"] is None
    assert no_project_row["minutes"] == 10


def test_b28_daily_stats_rejects_days_zero(client):
    """TESTING.md B28: days must be >= 1."""
    response = client.get("/work-blocks/stats/daily", params={"days": 0})
    assert response.status_code == 422


def test_b29_daily_stats_rejects_days_over_90(client):
    """TESTING.md B29: days must be <= 90."""
    response = client.get("/work-blocks/stats/daily", params={"days": 91})
    assert response.status_code == 422


def test_b30_daily_stats_days_one_is_today_only(client):
    """TESTING.md B30: days=1 only returns rows whose UTC day is today."""
    now = datetime.now(timezone.utc)
    yesterday_start = (now - timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    yesterday_end = yesterday_start + timedelta(minutes=25)

    task = client.post("/tasks", json={"title": "Task"}).json()
    client.post(
        f"/tasks/{task['id']}/work-blocks",
        json={
            "started_at": yesterday_start.isoformat(),
            "ended_at": yesterday_end.isoformat(),
        },
    )
    client.post(f"/tasks/{task['id']}/work-blocks", json={"minutes": 5})

    response = client.get("/work-blocks/stats/daily", params={"days": 1})
    assert response.status_code == 200
    rows = response.json()

    today_str = now.date().isoformat()
    assert all(r["date"] == today_str for r in rows)
    assert any(r["minutes"] == 5 for r in rows)
