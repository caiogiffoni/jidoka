import pytest
from fastapi.testclient import TestClient

import auth
import db
import main


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
