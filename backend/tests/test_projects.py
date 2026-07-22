def test_b11_create_project(client):
    """TESTING.md B11: POST /projects returns id/name/created_at, no color_slot."""
    response = client.post("/projects", json={"name": "Alpha"})
    assert response.status_code == 201

    body = response.json()
    assert body["name"] == "Alpha"
    assert "id" in body
    assert "created_at" in body
    assert "color_slot" not in body


def test_b12_create_project_ordering_by_created_at(client):
    """TESTING.md B12: creation order tracks created_at, not a color_slot sequence."""
    alpha = client.post("/projects", json={"name": "Alpha"}).json()
    beta = client.post("/projects", json={"name": "Beta"}).json()
    assert alpha["created_at"] <= beta["created_at"]


def test_b13_create_project_requires_name(client):
    """TESTING.md B13: POST /projects with no name is rejected."""
    response = client.post("/projects", json={})
    assert response.status_code == 422


def test_b14_list_projects_ordered_by_created_at(client):
    """TESTING.md B14: GET /projects returns both, ordered by created_at ascending."""
    alpha = client.post("/projects", json={"name": "Alpha"}).json()
    beta = client.post("/projects", json={"name": "Beta"}).json()

    projects = client.get("/projects").json()
    ids = [p["id"] for p in projects]
    assert ids == [alpha["id"], beta["id"]]


def test_b31_create_project_with_description(client):
    """TESTING.md B31: POST /projects accepts an optional markdown description."""
    response = client.post(
        "/projects", json={"name": "Alpha", "description": "# Notes\n\nDetails."}
    )
    assert response.status_code == 201
    assert response.json()["description"] == "# Notes\n\nDetails."


def test_b32_create_project_description_defaults_null(client):
    """TESTING.md B32: description is optional and defaults to null."""
    response = client.post("/projects", json={"name": "Alpha"})
    assert response.status_code == 201
    assert response.json()["description"] is None


def test_b33_update_project_name_and_description(client):
    """TESTING.md B33: PATCH /projects/{id} replaces name and description."""
    project = client.post("/projects", json={"name": "Alpha"}).json()

    response = client.patch(
        f"/projects/{project['id']}",
        json={"name": "Alpha Renamed", "description": "Updated notes"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alpha Renamed"
    assert body["description"] == "Updated notes"


def test_b34_update_missing_project_404s(client):
    """TESTING.md B34: PATCH on a nonexistent project is a 404."""
    response = client.patch(
        "/projects/00000000-0000-0000-0000-000000000000",
        json={"name": "x"},
    )
    assert response.status_code == 404


def test_b35_delete_project(client):
    """TESTING.md B35: DELETE /projects/{id} removes it from the list."""
    project = client.post("/projects", json={"name": "Alpha"}).json()

    response = client.delete(f"/projects/{project['id']}")
    assert response.status_code == 204

    ids = [p["id"] for p in client.get("/projects").json()]
    assert project["id"] not in ids


def test_b36_delete_project_unlinks_tasks(client):
    """TESTING.md B36: deleting a project via the endpoint sets its tasks' project_id to null."""
    project = client.post("/projects", json={"name": "Alpha"}).json()
    task = client.post(
        "/tasks", json={"title": "Linked task", "project_id": project["id"]}
    ).json()

    response = client.delete(f"/projects/{project['id']}")
    assert response.status_code == 204

    tasks = client.get("/tasks").json()
    linked = next(t for t in tasks if t["id"] == task["id"])
    assert linked["project_id"] is None


def test_b37_delete_missing_project_404s(client):
    """TESTING.md B37: DELETE on a nonexistent project is a 404."""
    response = client.delete("/projects/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
