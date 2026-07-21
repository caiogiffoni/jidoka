def test_b1_health_check(client):
    """TESTING.md B1: GET /health returns {"ok": true}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
