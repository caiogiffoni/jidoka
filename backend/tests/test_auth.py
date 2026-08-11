import pytest
from fastapi.testclient import TestClient

import auth
import db
import main
import oauth as oauth_module
from models import User


@pytest.fixture()
def anon_client(session):
    """A client with no authenticated user (but still using the test session)."""
    main.app.dependency_overrides[db.get_session] = lambda: session
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


def _register(anon_client, email, username, password):
    return anon_client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password},
    )


def test_register_creates_user_and_returns_token(anon_client):
    response = _register(anon_client, "new@example.com", "newuser", "Password1!")
    assert response.status_code == 201
    data = response.json()
    assert "token" in data
    assert data["user"]["email"] == "new@example.com"
    assert data["user"]["username"] == "newuser"
    assert "id" in data["user"]


def test_register_rejects_duplicate_email(anon_client):
    _register(anon_client, "dup@example.com", "userone", "Password1!")
    response = _register(anon_client, "dup@example.com", "usertwo", "Password2!")
    assert response.status_code == 409
    assert "email" in response.json()["detail"]


def test_register_rejects_duplicate_username(anon_client):
    _register(anon_client, "one@example.com", "dupuser", "Password1!")
    response = _register(anon_client, "two@example.com", "dupuser", "Password2!")
    assert response.status_code == 409
    assert "username" in response.json()["detail"]


def test_register_rejects_password_without_special_character(anon_client):
    response = _register(anon_client, "weak@example.com", "weakuser", "Password1")
    assert response.status_code == 422


def test_register_rejects_short_password(anon_client):
    response = _register(anon_client, "short@example.com", "shortuser", "Pass1!")
    assert response.status_code == 422


def test_register_rejects_username_starting_with_number(anon_client):
    response = _register(anon_client, "num@example.com", "1invalid", "Password1!")
    assert response.status_code == 422


def test_register_rejects_profane_username(anon_client):
    response = _register(anon_client, "profane@example.com", "fuck", "Password1!")
    assert response.status_code == 422


def test_login_returns_token_for_valid_credentials(anon_client):
    _register(anon_client, "login@example.com", "loginuser", "Password1!")
    response = anon_client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "Password1!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["email"] == "login@example.com"


def test_login_rejects_wrong_password(anon_client):
    _register(anon_client, "badpass@example.com", "badpassuser", "Password1!")
    response = anon_client.post(
        "/auth/login",
        json={"email": "badpass@example.com", "password": "WrongPassword1!"},
    )
    assert response.status_code == 401


def test_login_rejects_unknown_email(anon_client):
    response = anon_client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "Password1!"},
    )
    assert response.status_code == 401


def test_me_returns_current_user(anon_client):
    registered = _register(
        anon_client, "me@example.com", "meuser", "Password1!"
    ).json()
    token = registered["token"]
    response = anon_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


def test_me_rejects_missing_token(anon_client):
    response = anon_client.get("/auth/me")
    assert response.status_code == 401


def test_me_rejects_invalid_token(anon_client):
    response = anon_client.get(
        "/auth/me", headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401


def test_logout_returns_no_content(anon_client):
    response = anon_client.post("/auth/logout")
    assert response.status_code == 204


@pytest.fixture()
def google_creds(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")


def test_oauth_initiate_redirects_to_provider(anon_client, google_creds):
    response = anon_client.get("/auth/oauth/google", follow_redirects=False)
    assert response.status_code == 307
    assert "accounts.google.com" in response.headers["location"]
    assert "client_id=google-client-id" in response.headers["location"]


def test_oauth_initiate_rejects_unknown_provider(anon_client):
    response = anon_client.get("/auth/oauth/unknown", follow_redirects=False)
    assert response.status_code == 404


def test_oauth_initiate_returns_503_when_unconfigured(anon_client, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    response = anon_client.get("/auth/oauth/google", follow_redirects=False)
    assert response.status_code == 503


def _google_state() -> str:
    return oauth_module._sign_state("google")


def test_oauth_callback_creates_user_and_redirects(anon_client, monkeypatch):
    async def fake_fetch(provider, code):
        assert provider == "google"
        return oauth_module.OAuthUserInfo(
            provider_id="google-123",
            email="oauthnew@example.com",
            email_verified=True,
            username_base="oauthnew",
        )

    monkeypatch.setattr(oauth_module, "fetch_userinfo", fake_fetch)

    state = _google_state()
    response = anon_client.get(
        "/auth/oauth/google/callback",
        params={"code": "valid-code", "state": state},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "http://localhost:3000/oauth/callback?token="
    )


def test_oauth_callback_links_verified_email_user(
    anon_client, monkeypatch, session
):
    existing = User(
        email="link@example.com",
        username="linkuser",
        hashed_password=auth._hash_password("Password1!"),
    )
    session.add(existing)
    session.commit()

    async def fake_fetch(provider, code):
        return oauth_module.OAuthUserInfo(
            provider_id="google-456",
            email="link@example.com",
            email_verified=True,
            username_base="linkuser",
        )

    monkeypatch.setattr(oauth_module, "fetch_userinfo", fake_fetch)

    state = _google_state()
    response = anon_client.get(
        "/auth/oauth/google/callback",
        params={"code": "valid-code", "state": state},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "token=" in response.headers["location"]


def test_oauth_callback_rejects_invalid_state(anon_client):
    response = anon_client.get(
        "/auth/oauth/google/callback",
        params={"code": "valid-code", "state": "invalid-state"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        "http://localhost:3000/oauth/callback?error=invalid_state"
    )


def test_oauth_callback_rejects_missing_code(anon_client):
    state = _google_state()
    response = anon_client.get(
        "/auth/oauth/google/callback",
        params={"state": state},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=missing_oauth_parameters" in response.headers["location"]
