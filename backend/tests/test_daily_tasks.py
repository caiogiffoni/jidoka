from datetime import datetime, timezone


def test_b60_create_project_requires_template_when_daily_enabled(client):
    """TESTING.md B60: daily_enabled without a daily_template is rejected."""
    response = client.post(
        "/projects", json={"name": "Alpha", "daily_enabled": True}
    )
    assert response.status_code == 422


def test_b61_create_project_with_daily_template(client):
    """TESTING.md B61: daily_template round-trips and strips blank checklist items."""
    response = client.post(
        "/projects",
        json={
            "name": "Alpha",
            "daily_enabled": True,
            "daily_template": {
                "title": "Standup",
                "description": "Notes",
                "checklist": ["Post update", "   "],
            },
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["daily_enabled"] is True
    assert body["daily_template"] == {
        "title": "Standup",
        "description": "Notes",
        "checklist": ["Post update"],
    }


def test_b62_create_project_daily_disabled_template_defaults_null(client):
    """TESTING.md B62: with daily_enabled omitted, daily_template defaults to null."""
    response = client.post("/projects", json={"name": "Alpha"})
    assert response.status_code == 201
    body = response.json()
    assert body["daily_enabled"] is False
    assert body["daily_template"] is None


def test_b63_update_project_requires_template_when_daily_enabled(client):
    """TESTING.md B63: PATCH /projects/{id} enforces the same daily_enabled/template pairing."""
    project = client.post("/projects", json={"name": "Alpha"}).json()
    response = client.patch(
        f"/projects/{project['id']}",
        json={"name": "Alpha", "daily_enabled": True},
    )
    assert response.status_code == 422


def test_b64_update_project_sets_daily_template(client):
    """TESTING.md B64: PATCH /projects/{id} can enable daily tasks and set the template."""
    project = client.post("/projects", json={"name": "Alpha"}).json()
    response = client.patch(
        f"/projects/{project['id']}",
        json={
            "name": "Alpha",
            "daily_enabled": True,
            "daily_template": {"checklist": ["Check the queue"]},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["daily_enabled"] is True
    assert body["daily_template"] == {
        "title": None,
        "description": None,
        "checklist": ["Check the queue"],
    }


def test_b65_generate_daily_tasks_returns_empty_with_no_due_projects(client):
    """TESTING.md B65: with no daily-enabled projects, generate is a no-op."""
    client.post("/projects", json={"name": "Alpha"})
    response = client.post("/projects/daily-tasks/generate")
    assert response.status_code == 201
    assert response.json() == []


def test_b66_generate_daily_tasks_creates_task_with_title_suffix(client):
    """TESTING.md B66: a due project generates one todo card named
    "Daily - DD-MM-YY - <project>", with the template title appended, using
    the template's description/checklist directly."""
    project = client.post(
        "/projects",
        json={
            "name": "Alpha",
            "daily_enabled": True,
            "daily_template": {
                "title": "Standup",
                "description": "Notes",
                "checklist": ["Post update"],
            },
        },
    ).json()

    response = client.post("/projects/daily-tasks/generate")
    assert response.status_code == 201
    created = response.json()
    assert len(created) == 1

    today = datetime.now(timezone.utc).date()
    task = created[0]
    assert task["title"] == f"Daily - {today:%d-%m-%y} - Alpha - Standup"
    assert task["description"] == "Notes"
    assert task["column_id"] == "todo"
    assert task["project_id"] == project["id"]
    assert task["checklist"] == [{"text": "Post update", "checked": False}]

    refreshed = next(
        p for p in client.get("/projects").json() if p["id"] == project["id"]
    )
    assert refreshed["daily_last_generated"] == today.isoformat()


def test_b67_generate_daily_tasks_omits_suffix_without_template_title(client):
    """TESTING.md B67: no template title means the card name has no " - <title>" suffix."""
    client.post(
        "/projects",
        json={
            "name": "Beta",
            "daily_enabled": True,
            "daily_template": {"checklist": ["Check the queue"]},
        },
    )

    response = client.post("/projects/daily-tasks/generate")
    today = datetime.now(timezone.utc).date()
    assert response.json()[0]["title"] == f"Daily - {today:%d-%m-%y} - Beta"


def test_b68_generate_daily_tasks_idempotent_same_day(client):
    """TESTING.md B68: calling generate twice in the same UTC day only creates once."""
    client.post(
        "/projects",
        json={
            "name": "Alpha",
            "daily_enabled": True,
            "daily_template": {"checklist": ["Post update"]},
        },
    )

    first = client.post("/projects/daily-tasks/generate")
    assert len(first.json()) == 1

    second = client.post("/projects/daily-tasks/generate")
    assert second.status_code == 201
    assert second.json() == []


def test_b69_generate_daily_tasks_handles_multiple_due_projects(client):
    """TESTING.md B69: every daily-enabled, not-yet-generated-today project gets a card."""
    client.post(
        "/projects",
        json={
            "name": "Alpha",
            "daily_enabled": True,
            "daily_template": {"checklist": ["a"]},
        },
    )
    client.post(
        "/projects",
        json={
            "name": "Beta",
            "daily_enabled": True,
            "daily_template": {"checklist": ["b"]},
        },
    )
    client.post("/projects", json={"name": "Gamma"})  # not daily-enabled

    response = client.post("/projects/daily-tasks/generate")
    created = response.json()
    today = datetime.now(timezone.utc).date()
    assert {t["title"] for t in created} == {
        f"Daily - {today:%d-%m-%y} - Alpha",
        f"Daily - {today:%d-%m-%y} - Beta",
    }
