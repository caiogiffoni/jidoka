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
