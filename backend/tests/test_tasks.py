def test_b2_create_task_defaults(client):
    """TESTING.md B2: POST /tasks with only a title fills in defaults."""
    response = client.post("/tasks", json={"title": "Test task"})
    assert response.status_code == 201

    body = response.json()
    assert body["column_id"] == "todo"
    assert body["project_id"] is None
    assert body["position"] == 0

    second = client.post("/tasks", json={"title": "Second task"})
    assert second.status_code == 201
    assert second.json()["position"] == 1


def test_b3_create_task_requires_title(client):
    """TESTING.md B3: POST /tasks with no title is rejected."""
    response = client.post("/tasks", json={})
    assert response.status_code == 422


def test_b4_create_task_rejects_bogus_column(client):
    """TESTING.md B4: column_id is a fixed todo/in_progress/done literal."""
    response = client.post("/tasks", json={"title": "x", "column_id": "bogus"})
    assert response.status_code == 422


def test_b5_list_tasks_ordering(client):
    """TESTING.md B5: ordered by column_id, then position, then created_at."""
    done = client.post("/tasks", json={"title": "Done task", "column_id": "done"}).json()
    in_progress = client.post(
        "/tasks", json={"title": "In-progress task", "column_id": "in_progress"}
    ).json()
    todo_1 = client.post("/tasks", json={"title": "Todo 1"}).json()
    todo_2 = client.post("/tasks", json={"title": "Todo 2"}).json()

    tasks = client.get("/tasks").json()
    ids = [t["id"] for t in tasks]
    assert ids == [done["id"], in_progress["id"], todo_1["id"], todo_2["id"]]


def test_b6_move_task_reindexes_source_column(client):
    """TESTING.md B6: moving a task reindexes the column it left, no gaps."""
    t0 = client.post("/tasks", json={"title": "t0"}).json()
    t1 = client.post("/tasks", json={"title": "t1"}).json()
    t2 = client.post("/tasks", json={"title": "t2"}).json()

    response = client.patch(
        f"/tasks/{t0['id']}/move", json={"column_id": "in_progress", "position": 0}
    )
    assert response.status_code == 200
    moved = response.json()
    assert moved["column_id"] == "in_progress"
    assert moved["position"] == 0

    tasks = client.get("/tasks").json()
    remaining_todo = sorted(
        (t for t in tasks if t["column_id"] == "todo"), key=lambda t: t["position"]
    )
    assert [t["id"] for t in remaining_todo] == [t1["id"], t2["id"]]
    assert [t["position"] for t in remaining_todo] == [0, 1]


def test_b7_move_task_rejects_negative_position(client):
    """TESTING.md B7: position must be >= 0."""
    task = client.post("/tasks", json={"title": "x"}).json()
    response = client.patch(
        f"/tasks/{task['id']}/move", json={"column_id": "todo", "position": -1}
    )
    assert response.status_code == 422


def test_b8_move_missing_task_404s(client):
    """TESTING.md B8: moving a task that doesn't exist is a 404."""
    response = client.patch(
        "/tasks/00000000-0000-0000-0000-000000000000/move",
        json={"column_id": "todo", "position": 0},
    )
    assert response.status_code == 404


def test_b9_delete_task_reindexes_column(client):
    """TESTING.md B9: deleting a task reindexes the column it left."""
    t0 = client.post("/tasks", json={"title": "t0"}).json()
    t1 = client.post("/tasks", json={"title": "t1"}).json()
    t2 = client.post("/tasks", json={"title": "t2"}).json()

    response = client.delete(f"/tasks/{t1['id']}")
    assert response.status_code == 204

    tasks = client.get("/tasks").json()
    ids = [t["id"] for t in tasks]
    assert t1["id"] not in ids

    remaining_todo = sorted(
        (t for t in tasks if t["column_id"] == "todo"), key=lambda t: t["position"]
    )
    assert [t["id"] for t in remaining_todo] == [t0["id"], t2["id"]]
    assert [t["position"] for t in remaining_todo] == [0, 1]


def test_b10_delete_missing_task_404s(client):
    """TESTING.md B10: deleting a task that doesn't exist is a 404."""
    response = client.delete("/tasks/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_b41_update_task_title_description_and_project(client):
    """TESTING.md B41: PATCH /tasks/{id} replaces title, description, and project_id."""
    project = client.post("/projects", json={"name": "Alpha"}).json()
    task = client.post("/tasks", json={"title": "Original"}).json()

    response = client.patch(
        f"/tasks/{task['id']}",
        json={
            "title": "Renamed",
            "description": "Updated notes",
            "project_id": project["id"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Renamed"
    assert body["description"] == "Updated notes"
    assert body["project_id"] == project["id"]


def test_b42_update_task_can_unlink_project(client):
    """TESTING.md B42: omitting project_id on update clears an existing link."""
    project = client.post("/projects", json={"name": "Alpha"}).json()
    task = client.post(
        "/tasks", json={"title": "Linked", "project_id": project["id"]}
    ).json()

    response = client.patch(
        f"/tasks/{task['id']}", json={"title": "Linked", "description": None}
    )
    assert response.status_code == 200
    assert response.json()["project_id"] is None


def test_b43_update_task_rejects_missing_project(client):
    """TESTING.md B43: updating to a nonexistent project_id is a 404, not a 500."""
    task = client.post("/tasks", json={"title": "x"}).json()
    response = client.patch(
        f"/tasks/{task['id']}",
        json={
            "title": "x",
            "project_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code == 404


def test_b44_update_missing_task_404s(client):
    """TESTING.md B44: PATCH on a nonexistent task is a 404."""
    response = client.patch(
        "/tasks/00000000-0000-0000-0000-000000000000",
        json={"title": "x"},
    )
    assert response.status_code == 404


def test_b45_update_task_requires_title(client):
    """TESTING.md B45: PATCH /tasks/{id} without a title is rejected."""
    task = client.post("/tasks", json={"title": "x"}).json()
    response = client.patch(f"/tasks/{task['id']}", json={})
    assert response.status_code == 422


def test_b46_create_task_accepts_backlog_column(client):
    """TESTING.md B46: "backlog" is a valid column_id, ordered before "todo"."""
    backlog = client.post(
        "/tasks", json={"title": "Someday", "column_id": "backlog"}
    )
    assert backlog.status_code == 201
    assert backlog.json()["column_id"] == "backlog"

    todo = client.post("/tasks", json={"title": "Now"}).json()
    tasks = client.get("/tasks").json()
    ids = [t["id"] for t in tasks]
    assert ids.index(backlog.json()["id"]) < ids.index(todo["id"])
