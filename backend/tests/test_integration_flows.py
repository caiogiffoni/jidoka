"""Integration tests - unlike the rest of backend/tests/, which each check
one endpoint's contract in isolation, these chain several endpoint calls
together the way a real user session (or the future agent's apply node)
actually would, to catch bugs that only show up across a sequence of calls.
"""

from datetime import datetime, timezone


def test_i1_task_state_survives_a_realistic_chain_of_edits(client):
    """A task's project link, checklist, and due date all have to survive a
    realistic sequence of edits/moves/archive/unarchive - not just a single
    isolated PATCH. PATCH /tasks/{id} is a full replace (see B55/B56/B58),
    so each step below only works if the caller carries every prior field
    forward - the exact contract that's easy to get right in one test and
    silently break three edits later.
    """
    project = client.post("/projects", json={"name": "Launch"}).json()
    task = client.post(
        "/tasks",
        json={
            "title": "Ship it",
            "project_id": project["id"],
            "checklist": [{"text": "Write tests"}, {"text": "Deploy"}],
        },
    ).json()

    # The edit form sets a due date later - must carry the checklist
    # through, or this step would silently wipe it (B56's gotcha).
    with_due_date = client.patch(
        f"/tasks/{task['id']}",
        json={
            "title": task["title"],
            "project_id": project["id"],
            "checklist": task["checklist"],
            "due_date": "2026-08-01",
        },
    ).json()
    assert with_due_date["checklist"] == task["checklist"]
    assert with_due_date["due_date"] == "2026-08-01"

    # The board checks off an item - must carry the due date through this
    # time, or *that* silently vanishes instead (B58's gotcha).
    checked_off = [
        dict(item, checked=True) if item["text"] == "Write tests" else item
        for item in with_due_date["checklist"]
    ]
    with_checked_item = client.patch(
        f"/tasks/{task['id']}",
        json={
            "title": task["title"],
            "project_id": project["id"],
            "checklist": checked_off,
            "due_date": with_due_date["due_date"],
        },
    ).json()
    assert with_checked_item["due_date"] == "2026-08-01"
    assert with_checked_item["checklist"][0]["checked"] is True

    # Drag to in_progress, then archive it - project link, checklist, and
    # due date are untouched by either move or archive.
    client.patch(
        f"/tasks/{task['id']}/move",
        json={"column_id": "in_progress", "position": 0},
    )
    archived = client.patch(
        f"/tasks/{task['id']}/archive", json={"archived": True}
    ).json()
    assert archived["column_id"] == "in_progress"
    assert archived["project_id"] == project["id"]
    assert archived["due_date"] == "2026-08-01"
    assert archived["checklist"][0]["checked"] is True

    # Unarchive - still everything, still linked, still in_progress.
    unarchived = client.patch(
        f"/tasks/{task['id']}/archive", json={"archived": False}
    ).json()
    assert unarchived["column_id"] == "in_progress"
    assert unarchived["project_id"] == project["id"]
    assert unarchived["due_date"] == "2026-08-01"
    assert unarchived["checklist"] == checked_off


def test_i2_daily_generated_task_rolls_up_into_dashboard_then_survives_project_deletion(
    client,
):
    """A daily-generated task (POST /projects/daily-tasks/generate) is a
    real task like any other, not a special case: logging time against it
    rolls up into the dashboard stats attributed to its project (same as a
    manually-created task, see B27), and deleting the project later unlinks
    - not deletes - the task and keeps its logged time, same as B36.
    """
    project = client.post(
        "/projects",
        json={
            "name": "Ops",
            "daily_enabled": True,
            "daily_template": {"title": "Standup", "checklist": ["Post update"]},
        },
    ).json()

    generated = client.post("/projects/daily-tasks/generate").json()
    assert len(generated) == 1
    task = generated[0]
    assert task["project_id"] == project["id"]

    today = datetime.now(timezone.utc).date().isoformat()
    client.post(
        f"/tasks/{task['id']}/work-blocks",
        json={
            "started_at": f"{today}T09:00:00Z",
            "ended_at": f"{today}T09:25:00Z",
        },
    )

    stats = client.get("/work-blocks/stats/daily?days=1").json()
    ops_row = next(r for r in stats if r["project_id"] == project["id"])
    assert ops_row["project_name"] == "Ops"
    assert ops_row["minutes"] == 25

    # Deleting the project unlinks the generated task rather than deleting
    # it, and its logged time survives - just relabeled "no project" going
    # forward, same as any manually-created task's time would be.
    client.delete(f"/projects/{project['id']}")

    survivors = client.get("/tasks").json()
    linked = next(t for t in survivors if t["id"] == task["id"])
    assert linked["project_id"] is None

    stats_after = client.get("/work-blocks/stats/daily?days=1").json()
    unlabeled_row = next(r for r in stats_after if r["project_id"] is None)
    assert unlabeled_row["minutes"] >= 25
