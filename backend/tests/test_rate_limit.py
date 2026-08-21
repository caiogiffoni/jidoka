"""Rate limiting regression tests."""


def test_login_rate_limit_blocks_after_threshold(anon_client):
    """Repeated failed logins from the same IP hit the 10/minute ceiling."""
    for _ in range(10):
        response = anon_client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "wrong"},
        )
        assert response.status_code == 401

    blocked = anon_client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    assert blocked.status_code == 429
    assert "rate limit" in blocked.text.lower() or "too many" in blocked.text.lower()
