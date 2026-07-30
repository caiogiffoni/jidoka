"""Move semantics: position is display order within a column and stays dense
(0..n-1) after every move; both source and destination columns are reindexed,
out-of-range positions clamp to the end, and unknown column ids are rejected.
"""


def _column(client, column_id):
    """Tasks of one column, in display order (GET /tasks sorts by position)."""
    tasks = client.get("/tasks").json()
    return [t for t in tasks if t["column_id"] == column_id]


def test_within_column_reorder_keeps_positions_dense(client):
    first = client.post("/tasks", json={"title": "First"}).json()
    client.post("/tasks", json={"title": "Second"})
    client.post("/tasks", json={"title": "Third"})

    response = client.patch(
        f"/tasks/{first['id']}/move",
        json={"column_id": "todo", "position": 2},
    )
    assert response.status_code == 200

    column = _column(client, "todo")
    assert [t["title"] for t in column] == ["Second", "Third", "First"]
    assert [t["position"] for t in column] == [0, 1, 2]


def test_cross_column_move_reindexes_destination_column(client):
    client.post("/tasks", json={"title": "DoneOne", "column_id": "done"})
    client.post("/tasks", json={"title": "DoneTwo", "column_id": "done"})
    task = client.post("/tasks", json={"title": "Mover"}).json()

    response = client.patch(
        f"/tasks/{task['id']}/move",
        json={"column_id": "done", "position": 1},
    )
    assert response.status_code == 200

    column = _column(client, "done")
    assert [t["title"] for t in column] == ["DoneOne", "Mover", "DoneTwo"]
    assert [t["position"] for t in column] == [0, 1, 2]


def test_move_position_beyond_column_length_is_clamped_to_end(client):
    client.post("/tasks", json={"title": "DoneOne", "column_id": "done"})
    task = client.post("/tasks", json={"title": "Mover"}).json()

    response = client.patch(
        f"/tasks/{task['id']}/move",
        json={"column_id": "done", "position": 99},
    )
    assert response.status_code == 200
    assert response.json()["position"] == 1

    column = _column(client, "done")
    assert [t["title"] for t in column] == ["DoneOne", "Mover"]
    assert [t["position"] for t in column] == [0, 1]


def test_move_rejects_unknown_column_id(client):
    task = client.post("/tasks", json={"title": "Task"}).json()

    response = client.patch(
        f"/tasks/{task['id']}/move",
        json={"column_id": "limbo", "position": 0},
    )
    assert response.status_code == 422


def test_move_to_position_zero_puts_task_first(client):
    client.post("/tasks", json={"title": "First"})
    second = client.post("/tasks", json={"title": "Second"}).json()

    response = client.patch(
        f"/tasks/{second['id']}/move",
        json={"column_id": "todo", "position": 0},
    )
    assert response.status_code == 200

    column = _column(client, "todo")
    assert [t["title"] for t in column] == ["Second", "First"]
    assert [t["position"] for t in column] == [0, 1]
