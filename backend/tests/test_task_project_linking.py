import uuid

from models import Project


def test_b15_create_task_linked_to_project(client):
    """TESTING.md B15: POST /tasks with a project_id links the task."""
    project = client.post("/projects", json={"name": "Alpha"}).json()

    response = client.post(
        "/tasks", json={"title": "Linked task", "project_id": project["id"]}
    )
    assert response.status_code == 201
    assert response.json()["project_id"] == project["id"]


def test_b16_create_task_with_missing_project_404s(client):
    """TESTING.md B16: a nonexistent project_id is a 404, not a raw FK 500."""
    response = client.post(
        "/tasks",
        json={
            "title": "x",
            "project_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code == 404


def test_b17_deleting_project_unlinks_task(client, session):
    """TESTING.md B17: deleting a project sets its tasks' project_id to null."""
    project = client.post("/projects", json={"name": "Alpha"}).json()
    task = client.post(
        "/tasks", json={"title": "Linked task", "project_id": project["id"]}
    ).json()

    db_project = session.get(Project, uuid.UUID(project["id"]))
    session.delete(db_project)
    session.commit()

    tasks = client.get("/tasks").json()
    linked = next(t for t in tasks if t["id"] == task["id"])
    assert linked["project_id"] is None
