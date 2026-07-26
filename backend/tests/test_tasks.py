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
    """TESTING.md B5: ordered by column_id, then position, then created_at.

    Checks relative order (not exact list equality) so this passes against a
    dev DB that already has other tasks in it, not just an empty one.
    """
    done = client.post("/tasks", json={"title": "Done task", "column_id": "done"}).json()
    in_progress = client.post(
        "/tasks", json={"title": "In-progress task", "column_id": "in_progress"}
    ).json()
    todo_1 = client.post("/tasks", json={"title": "Todo 1"}).json()
    todo_2 = client.post("/tasks", json={"title": "Todo 2"}).json()

    ids = [t["id"] for t in client.get("/tasks").json()]
    assert ids.index(done["id"]) < ids.index(in_progress["id"])
    assert ids.index(in_progress["id"]) < ids.index(todo_1["id"])
    assert ids.index(todo_1["id"]) < ids.index(todo_2["id"])


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


def test_b53_create_task_with_checklist_defaults_unchecked(client):
    """TESTING.md B53: POST /tasks accepts a checklist; items default checked=false."""
    response = client.post(
        "/tasks",
        json={"title": "x", "checklist": [{"text": "Item one"}, {"text": "Item two"}]},
    )
    assert response.status_code == 201
    assert response.json()["checklist"] == [
        {"text": "Item one", "checked": False},
        {"text": "Item two", "checked": False},
    ]


def test_b54_create_task_strips_blank_checklist_items(client):
    """TESTING.md B54: blank/whitespace-only checklist item text is dropped on create."""
    response = client.post(
        "/tasks",
        json={"title": "x", "checklist": [{"text": "  Keep me  "}, {"text": "   "}]},
    )
    assert response.status_code == 201
    assert response.json()["checklist"] == [{"text": "Keep me", "checked": False}]


def test_b55_update_task_replaces_checklist(client):
    """TESTING.md B55: PATCH /tasks/{id} replaces the checklist (full replace)."""
    task = client.post(
        "/tasks", json={"title": "x", "checklist": [{"text": "Old"}]}
    ).json()

    response = client.patch(
        f"/tasks/{task['id']}",
        json={
            "title": "x",
            "checklist": [{"text": "New", "checked": True}],
        },
    )
    assert response.status_code == 200
    assert response.json()["checklist"] == [{"text": "New", "checked": True}]


def test_b56_update_task_omitting_checklist_wipes_it(client):
    """TESTING.md B56: full-replace PATCH clears an existing checklist if the caller omits it."""
    task = client.post(
        "/tasks", json={"title": "x", "checklist": [{"text": "Will vanish"}]}
    ).json()

    response = client.patch(f"/tasks/{task['id']}", json={"title": "x"})
    assert response.status_code == 200
    assert response.json()["checklist"] == []


def test_b57_create_task_has_no_due_date_and_update_sets_it(client):
    """TESTING.md B57: due_date isn't settable at creation (TaskCreate has no such
    field); PATCH /tasks/{id} is what sets it, and it round-trips unchanged."""
    created = client.post("/tasks", json={"title": "x"})
    assert created.status_code == 201
    assert created.json()["due_date"] is None

    updated = client.patch(
        f"/tasks/{created.json()['id']}",
        json={"title": "x", "due_date": "2026-09-15"},
    )
    assert updated.status_code == 200
    assert updated.json()["due_date"] == "2026-09-15"


def test_b58_update_task_omitting_due_date_clears_it(client):
    """TESTING.md B58: full-replace PATCH clears an existing due_date if the caller omits it."""
    task = client.post(
        "/tasks", json={"title": "x", "due_date": "2026-08-01"}
    ).json()

    response = client.patch(f"/tasks/{task['id']}", json={"title": "x"})
    assert response.status_code == 200
    assert response.json()["due_date"] is None


def test_b59_update_task_rejects_bogus_due_date(client):
    """TESTING.md B59: an unparseable due_date is a 422, not a 500."""
    task = client.post("/tasks", json={"title": "x"}).json()
    response = client.patch(
        f"/tasks/{task['id']}", json={"title": "x", "due_date": "not-a-date"}
    )
    assert response.status_code == 422
