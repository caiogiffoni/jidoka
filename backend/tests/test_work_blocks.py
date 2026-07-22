import uuid

from sqlmodel import select

from models import WorkBlock


def test_b18_create_timed_work_block(client):
    """TESTING.md B18: a timed work block gets minutes computed from the duration."""
    task = client.post("/tasks", json={"title": "Task"}).json()
    response = client.post(
        f"/tasks/{task['id']}/work-blocks",
        json={
            "started_at": "2026-07-14T10:00:00Z",
            "ended_at": "2026-07-14T10:25:00Z",
        },
    )
    assert response.status_code == 201
    assert response.json()["minutes"] == 25


def test_timed_work_block_minutes_rounds_partial_duration(client):
    """A non-whole-minute duration still stores a rounded minutes value."""
    task = client.post("/tasks", json={"title": "Task"}).json()
    response = client.post(
        f"/tasks/{task['id']}/work-blocks",
        json={
            "started_at": "2026-07-14T10:00:00Z",
            "ended_at": "2026-07-14T10:07:40Z",  # 7 min 40 sec -> rounds to 8
        },
    )
    assert response.status_code == 201
    assert response.json()["minutes"] == 8


def test_b19_create_manual_work_block(client):
    """TESTING.md B19: a manual entry (logged independent of the pomodoro
    timer) has started_at/ended_at == null and keeps the minutes given."""
    task = client.post("/tasks", json={"title": "Task"}).json()
    response = client.post(f"/tasks/{task['id']}/work-blocks", json={"minutes": 15})
    assert response.status_code == 201

    body = response.json()
    assert body["started_at"] is None
    assert body["ended_at"] is None
    assert body["minutes"] == 15
    assert body["created_at"] is not None


def test_b20_create_work_block_requires_timed_or_minutes(client):
    """TESTING.md B20: neither timed fields nor minutes is rejected."""
    task = client.post("/tasks", json={"title": "Task"}).json()
    response = client.post(f"/tasks/{task['id']}/work-blocks", json={})
    assert response.status_code == 422


def test_b21_create_work_block_rejects_zero_minutes(client):
    """TESTING.md B21: minutes must be >= 1."""
    task = client.post("/tasks", json={"title": "Task"}).json()
    response = client.post(f"/tasks/{task['id']}/work-blocks", json={"minutes": 0})
    assert response.status_code == 422


def test_b22_create_work_block_rejects_ended_before_started(client):
    """TESTING.md B22: ended_at before started_at is rejected."""
    task = client.post("/tasks", json={"title": "Task"}).json()
    response = client.post(
        f"/tasks/{task['id']}/work-blocks",
        json={
            "started_at": "2026-07-14T11:00:00Z",
            "ended_at": "2026-07-14T10:00:00Z",
        },
    )
    assert response.status_code == 422


def test_b23_create_work_block_missing_task_404s(client):
    """TESTING.md B23: logging time against a nonexistent task is a 404."""
    response = client.post(
        "/tasks/00000000-0000-0000-0000-000000000000/work-blocks",
        json={"minutes": 5},
    )
    assert response.status_code == 404


def test_b24_list_work_blocks_ordering(client):
    """TESTING.md B24: ordered by started_at, then created_at."""
    task = client.post("/tasks", json={"title": "Task"}).json()
    timed = client.post(
        f"/tasks/{task['id']}/work-blocks",
        json={
            "started_at": "2026-07-14T10:00:00Z",
            "ended_at": "2026-07-14T10:25:00Z",
        },
    ).json()
    manual = client.post(f"/tasks/{task['id']}/work-blocks", json={"minutes": 15}).json()

    blocks = client.get(f"/tasks/{task['id']}/work-blocks").json()
    assert [b["id"] for b in blocks] == [timed["id"], manual["id"]]


def test_b25_delete_task_cascades_work_blocks(client, session):
    """TESTING.md B25: deleting a task cascade-deletes its work blocks."""
    task = client.post("/tasks", json={"title": "Task"}).json()
    client.post(f"/tasks/{task['id']}/work-blocks", json={"minutes": 15})

    response = client.delete(f"/tasks/{task['id']}")
    assert response.status_code == 204

    remaining = session.exec(
        select(WorkBlock).where(WorkBlock.task_id == uuid.UUID(task["id"]))
    ).all()
    assert remaining == []
