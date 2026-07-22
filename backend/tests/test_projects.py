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
