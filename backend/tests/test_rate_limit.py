"""Rate limiting regression tests."""

import pytest
from starlette.requests import Request

import auth
from rate_limit import CLIENT_IP_HEADER, PROXY_SECRET_HEADER, client_ip, user_or_ip_key


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


SECRET = "test-proxy-secret"


def _request(headers: dict[str, str], host: str = "10.0.0.1") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": (host, 12345),
        }
    )


@pytest.fixture()
def proxy_secret(monkeypatch):
    monkeypatch.setenv("INTERNAL_PROXY_SECRET", SECRET)


def test_client_ip_ignores_forwarded_header_without_configured_secret(monkeypatch):
    monkeypatch.delenv("INTERNAL_PROXY_SECRET", raising=False)
    request = _request({CLIENT_IP_HEADER: "1.2.3.4", PROXY_SECRET_HEADER: ""})
    assert client_ip(request) == "10.0.0.1"


def test_client_ip_ignores_forwarded_header_with_wrong_secret(proxy_secret):
    request = _request({CLIENT_IP_HEADER: "1.2.3.4", PROXY_SECRET_HEADER: "nope"})
    assert client_ip(request) == "10.0.0.1"


def test_client_ip_ignores_forwarded_header_with_missing_secret(proxy_secret):
    assert client_ip(_request({CLIENT_IP_HEADER: "1.2.3.4"})) == "10.0.0.1"


def test_client_ip_trusts_forwarded_header_with_valid_secret(proxy_secret):
    request = _request(
        {CLIENT_IP_HEADER: "1.2.3.4, 5.6.7.8", PROXY_SECRET_HEADER: SECRET}
    )
    assert client_ip(request) == "1.2.3.4"


def test_client_ip_falls_back_on_malformed_forwarded_ip(proxy_secret):
    request = _request({CLIENT_IP_HEADER: "not-an-ip", PROXY_SECRET_HEADER: SECRET})
    assert client_ip(request) == "10.0.0.1"


def test_user_or_ip_key_uses_user_id_for_valid_token(anon_client):
    token = anon_client.post(
        "/auth/register",
        json={"email": "key@example.com", "username": "keyuser", "password": "Password1!"},
    ).json()["token"]
    sub = auth._decode_token(token)["sub"]
    assert user_or_ip_key(_request({"Authorization": f"Bearer {token}"})) == f"user:{sub}"


def test_user_or_ip_key_falls_back_to_ip_for_bad_token():
    request = _request({"Authorization": "Bearer garbage"})
    assert user_or_ip_key(request) == "ip:10.0.0.1"


def _bad_login(client, email, ip=None, secret=SECRET):
    headers = {}
    if ip is not None:
        headers = {CLIENT_IP_HEADER: ip, PROXY_SECRET_HEADER: secret}
    return client.post(
        "/auth/login", json={"email": email, "password": "wrong"}, headers=headers
    )


def test_distinct_forwarded_ips_get_independent_buckets(anon_client, proxy_secret):
    # Distinct emails so only the per-IP limit is in play.
    for i in range(10):
        assert _bad_login(anon_client, f"a{i}@example.com", ip="1.1.1.1").status_code == 401
    assert _bad_login(anon_client, "a10@example.com", ip="1.1.1.1").status_code == 429
    # A different client behind the same proxy is unaffected.
    assert _bad_login(anon_client, "b@example.com", ip="2.2.2.2").status_code == 401


def test_spoofed_forwarded_ip_without_secret_shares_socket_bucket(anon_client, proxy_secret):
    for i in range(10):
        response = _bad_login(anon_client, f"s{i}@example.com", ip=f"9.9.9.{i}", secret="bad")
        assert response.status_code == 401
    assert _bad_login(anon_client, "s10@example.com", ip="9.9.9.99", secret="bad").status_code == 429


def test_login_email_limited_across_many_ips(anon_client, proxy_secret):
    for i in range(10):
        assert _bad_login(anon_client, "Victim@example.com", ip=f"3.3.3.{i}").status_code == 401
    # Fresh IP, same account (different casing): blocked by the per-email limit.
    blocked = _bad_login(anon_client, "victim@EXAMPLE.com", ip="4.4.4.4")
    assert blocked.status_code == 429
    # Other accounts from that IP still work.
    assert _bad_login(anon_client, "other@example.com", ip="4.4.4.4").status_code == 401


def test_successful_logins_do_not_consume_email_budget(anon_client, proxy_secret):
    anon_client.post(
        "/auth/register",
        json={"email": "ok@example.com", "username": "okuser", "password": "Password1!"},
    )
    for i in range(12):
        response = anon_client.post(
            "/auth/login",
            json={"email": "ok@example.com", "password": "Password1!"},
            headers={CLIENT_IP_HEADER: f"5.5.5.{i}", PROXY_SECRET_HEADER: SECRET},
        )
        assert response.status_code == 200
