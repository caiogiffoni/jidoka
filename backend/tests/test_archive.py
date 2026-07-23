def test_b47_create_task_defaults_unarchived(client):
    """TESTING.md B47: new tasks default to archived: false."""
    task = client.post("/tasks", json={"title": "x"}).json()
    assert task["archived"] is False


def test_b48_archive_task_hides_from_default_list(client):
    """TESTING.md B48: archiving a task removes it from GET /tasks by default."""
    task = client.post("/tasks", json={"title": "x"}).json()

    response = client.patch(f"/tasks/{task['id']}/archive", json={"archived": True})
    assert response.status_code == 200
    assert response.json()["archived"] is True

    ids = [t["id"] for t in client.get("/tasks").json()]
    assert task["id"] not in ids


def test_b49_archive_task_reindexes_column(client):
    """TESTING.md B49: archiving reindexes the column it leaves, no gaps."""
    t0 = client.post("/tasks", json={"title": "t0"}).json()
    t1 = client.post("/tasks", json={"title": "t1"}).json()
    t2 = client.post("/tasks", json={"title": "t2"}).json()

    response = client.patch(f"/tasks/{t1['id']}/archive", json={"archived": True})
    assert response.status_code == 200

    remaining = sorted(
        (t for t in client.get("/tasks").json() if t["column_id"] == "todo"),
        key=lambda t: t["position"],
    )
    assert [t["id"] for t in remaining] == [t0["id"], t2["id"]]
    assert [t["position"] for t in remaining] == [0, 1]


def test_b50_include_archived_query_param_shows_archived(client):
    """TESTING.md B50: GET /tasks?include_archived=true surfaces archived tasks too."""
    task = client.post("/tasks", json={"title": "x"}).json()
    client.patch(f"/tasks/{task['id']}/archive", json={"archived": True})

    ids = [t["id"] for t in client.get("/tasks?include_archived=true").json()]
    assert task["id"] in ids


def test_b51_unarchive_task_reappends_to_column(client):
    """TESTING.md B51: setting archived back to false re-adds the task at the end of its column."""
    task = client.post("/tasks", json={"title": "x"}).json()
    client.patch(f"/tasks/{task['id']}/archive", json={"archived": True})
    other = client.post("/tasks", json={"title": "y"}).json()

    response = client.patch(f"/tasks/{task['id']}/archive", json={"archived": False})
    assert response.status_code == 200
    body = response.json()
    assert body["archived"] is False
    assert body["position"] == 1

    ids = [t["id"] for t in client.get("/tasks").json() if t["column_id"] == "todo"]
    assert ids == [other["id"], task["id"]]


def test_b52_archive_missing_task_404s(client):
    """TESTING.md B52: archiving a task that doesn't exist is a 404."""
    response = client.patch(
        "/tasks/00000000-0000-0000-0000-000000000000/archive",
        json={"archived": True},
    )
    assert response.status_code == 404
