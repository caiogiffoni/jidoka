from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

import auth
import db
import main
import oauth as oauth_module
from models import OAuthExchangeCode, User


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


def test_register_rejects_password_over_72_bytes(anon_client):
    response = _register(anon_client, "long@example.com", "longuser", "a!" * 37)
    assert response.status_code == 422
    assert "72 bytes" in response.text


def test_register_measures_password_length_in_utf8_bytes(anon_client):
    # 37 characters but 73 bytes: each "é" is 2 bytes in UTF-8.
    password = "!" + "é" * 36
    assert len(password) < 72 < len(password.encode("utf-8"))
    response = _register(anon_client, "utf8@example.com", "utf8user", password)
    assert response.status_code == 422


def test_register_accepts_password_of_exactly_72_bytes(anon_client):
    password = "!" + "a" * 71
    response = _register(anon_client, "exact@example.com", "exactuser", password)
    assert response.status_code == 201
    login = anon_client.post(
        "/auth/login", json={"email": "exact@example.com", "password": password}
    )
    assert login.status_code == 200


def test_login_with_password_over_72_bytes_is_401_not_500(anon_client):
    _register(anon_client, "longlogin@example.com", "longlogin", "Password1!")
    response = anon_client.post(
        "/auth/login",
        json={"email": "longlogin@example.com", "password": "Password1!" * 10},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid email or password"


def test_register_normalizes_email(anon_client):
    response = _register(anon_client, "  Mixed@Example.COM ", "mixeduser", "Password1!")
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "mixed@example.com"


def test_register_rejects_duplicate_email_case_insensitively(anon_client):
    assert _register(anon_client, "Foo@x.com", "fooone", "Password1!").status_code == 201
    response = _register(anon_client, "foo@X.com", "footwo", "Password2!")
    assert response.status_code == 409
    assert response.json()["detail"] == "email already registered"


def test_register_duplicate_check_matches_legacy_mixed_case_rows(anon_client, session):
    session.add(
        User(
            email="Legacy@Example.com",
            username="legacyuser",
            hashed_password=auth._hash_password("Password1!"),
        )
    )
    session.flush()
    response = _register(anon_client, "legacy@example.com", "legacytwo", "Password1!")
    assert response.status_code == 409


def test_login_is_case_insensitive(anon_client):
    _register(anon_client, "case@example.com", "caseuser", "Password1!")
    response = anon_client.post(
        "/auth/login", json={"email": "CASE@Example.com", "password": "Password1!"}
    )
    assert response.status_code == 200


def test_login_matches_legacy_mixed_case_rows(anon_client, session):
    session.add(
        User(
            email="OldUser@Example.com",
            username="olduser",
            hashed_password=auth._hash_password("Password1!"),
        )
    )
    session.flush()
    response = anon_client.post(
        "/auth/login", json={"email": "olduser@example.com", "password": "Password1!"}
    )
    assert response.status_code == 200


def test_register_race_integrity_error_returns_409(anon_client, monkeypatch):
    """Two concurrent registrations can both pass the pre-check; the loser's
    unique-constraint violation must surface as the same 409, not a 500."""
    assert _register(anon_client, "race@example.com", "raceone", "Password1!").status_code == 201

    real_conflict = auth._registration_conflict
    calls = {"n": 0}

    def skip_first_check(*args, **kwargs):
        # Simulate losing the race: the pre-check sees no row, the post-
        # IntegrityError lookup sees the winner.
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return real_conflict(*args, **kwargs)

    monkeypatch.setattr(auth, "_registration_conflict", skip_first_check)
    response = _register(anon_client, "race@example.com", "racetwo", "Password1!")
    assert response.status_code == 409
    assert response.json()["detail"] == "email already registered"
    assert calls["n"] == 2


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


def test_oauth_initiate_sets_browser_bound_state_cookie(anon_client, google_creds):
    response = anon_client.get("/auth/oauth/google", follow_redirects=False)
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{oauth_module.STATE_COOKIE}=")
    assert "HttpOnly" in set_cookie
    assert "Path=/auth/oauth" in set_cookie
    assert "samesite=lax" in set_cookie.lower()
    # Plain-HTTP dev backend: not Secure (it would never be sent back).
    assert "Secure" not in set_cookie

    nonce = response.cookies[oauth_module.STATE_COOKIE]
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    assert oauth_module._verify_state(state, "google", nonce) is True


def test_oauth_initiate_state_cookie_is_secure_over_https(
    anon_client, google_creds, monkeypatch
):
    monkeypatch.setenv("BACKEND_URL", "https://api.example.com")
    response = anon_client.get("/auth/oauth/google", follow_redirects=False)
    assert "Secure" in response.headers["set-cookie"]


def _start_flow(anon_client) -> str:
    """Hit the initiate endpoint so the client holds the state cookie, and
    return the matching state value."""
    response = anon_client.get("/auth/oauth/google", follow_redirects=False)
    return parse_qs(urlparse(response.headers["location"]).query)["state"][0]


def _fake_userinfo(monkeypatch, **overrides):
    info = dict(
        provider_id="google-123",
        email="oauthnew@example.com",
        email_verified=True,
        username_base="oauthnew",
    )
    info.update(overrides)

    async def fake_fetch(provider, code):
        assert provider == "google"
        return oauth_module.OAuthUserInfo(**info)

    monkeypatch.setattr(oauth_module, "fetch_userinfo", fake_fetch)


def _callback(anon_client, state, code="valid-code"):
    return anon_client.get(
        "/auth/oauth/google/callback",
        params={"code": code, "state": state},
        follow_redirects=False,
    )


def _exchange_code_from(response) -> str:
    location = response.headers["location"]
    assert location.startswith("http://localhost:3000/oauth/callback?code=")
    return parse_qs(urlparse(location).query)["code"][0]


def test_oauth_callback_redirects_with_exchange_code_not_token(
    anon_client, monkeypatch, google_creds
):
    _fake_userinfo(monkeypatch)
    state = _start_flow(anon_client)

    response = _callback(anon_client, state)

    assert response.status_code == 303
    location = response.headers["location"]
    assert "token=" not in location
    code = _exchange_code_from(response)
    # The opaque code is not a JWT.
    assert code.count(".") == 0
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    # State cookie cleared after use.
    assert f'{oauth_module.STATE_COOKIE}=""' in response.headers["set-cookie"]


def test_oauth_exchange_returns_session_token_once(
    anon_client, monkeypatch, google_creds
):
    _fake_userinfo(monkeypatch)
    state = _start_flow(anon_client)
    code = _exchange_code_from(_callback(anon_client, state))

    first = anon_client.post("/auth/oauth/exchange", json={"code": code})
    assert first.status_code == 200
    body = first.json()
    assert body["user"]["email"] == "oauthnew@example.com"
    me = anon_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {body['token']}"}
    )
    assert me.status_code == 200

    second = anon_client.post("/auth/oauth/exchange", json={"code": code})
    assert second.status_code == 400


def test_oauth_exchange_rejects_expired_code(anon_client, session, test_user):
    code = oauth_module.issue_exchange_code(session, test_user)
    row = session.exec(
        select(OAuthExchangeCode).where(
            OAuthExchangeCode.code_hash == oauth_module._hash(code)
        )
    ).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.add(row)
    session.commit()

    response = anon_client.post("/auth/oauth/exchange", json={"code": code})
    assert response.status_code == 400


def test_oauth_exchange_rejects_unknown_code(anon_client):
    response = anon_client.post("/auth/oauth/exchange", json={"code": "bogus"})
    assert response.status_code == 400


def test_oauth_callback_refuses_to_link_password_account(
    anon_client, monkeypatch, session, google_creds
):
    existing = User(
        email="Link@Example.com",
        username="linkuser",
        hashed_password=auth._hash_password("Password1!"),
    )
    session.add(existing)
    session.commit()
    _fake_userinfo(monkeypatch, provider_id="google-456", email="link@example.com")

    state = _start_flow(anon_client)
    response = _callback(anon_client, state)

    assert response.status_code == 303
    assert response.headers["location"] == (
        "http://localhost:3000/oauth/callback?error=account_exists_password"
    )
    session.refresh(existing)
    assert existing.oauth_provider is None


def test_oauth_callback_rejects_missing_state_cookie(
    anon_client, monkeypatch, google_creds
):
    _fake_userinfo(monkeypatch)
    state = _start_flow(anon_client)
    anon_client.cookies.clear()

    response = _callback(anon_client, state)

    assert response.headers["location"] == (
        "http://localhost:3000/oauth/callback?error=invalid_state"
    )


def test_oauth_callback_rejects_state_from_another_browser(
    anon_client, monkeypatch, google_creds
):
    """Login CSRF: an attacker's valid state is useless in the victim's
    browser, whose cookie holds a different nonce."""
    _fake_userinfo(monkeypatch)
    attacker_state, _ = oauth_module._sign_state("google")
    _start_flow(anon_client)  # victim has their own, different cookie

    response = _callback(anon_client, attacker_state)

    assert response.headers["location"] == (
        "http://localhost:3000/oauth/callback?error=invalid_state"
    )


def test_oauth_callback_state_cookie_is_single_use(
    anon_client, monkeypatch, google_creds
):
    _fake_userinfo(monkeypatch)
    state = _start_flow(anon_client)
    assert _callback(anon_client, state).headers["location"].startswith(
        "http://localhost:3000/oauth/callback?code="
    )

    replay = _callback(anon_client, state)
    assert replay.headers["location"].endswith("error=invalid_state")


def test_oauth_callback_rejects_invalid_state(anon_client, google_creds):
    _start_flow(anon_client)
    response = _callback(anon_client, "invalid-state")
    assert response.status_code == 303
    assert response.headers["location"] == (
        "http://localhost:3000/oauth/callback?error=invalid_state"
    )


def test_oauth_callback_rejects_missing_code(anon_client, google_creds):
    state = _start_flow(anon_client)
    response = anon_client.get(
        "/auth/oauth/google/callback",
        params={"state": state},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=missing_oauth_parameters" in response.headers["location"]


def test_oauth_callback_does_not_reflect_provider_error_text(
    anon_client, monkeypatch, google_creds
):
    async def failing_fetch(provider, code):
        raise RuntimeError("<script>alert(1)</script> something odd")

    monkeypatch.setattr(oauth_module, "fetch_userinfo", failing_fetch)
    state = _start_flow(anon_client)

    response = _callback(anon_client, state)

    assert response.headers["location"] == (
        "http://localhost:3000/oauth/callback?error=provider_request_failed"
    )


def _token_for(user: User, **claims) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "username": user.username,
        "iat": now,
        "exp": now + timedelta(days=1),
        **claims,
    }
    return jwt.encode(payload, auth._jwt_secret(), algorithm=auth.JWT_ALGORITHM)


def test_access_token_carries_access_typ(test_user):
    payload = auth._decode_token(auth._create_token(test_user))
    assert payload["typ"] == auth.ACCESS_TOKEN_TYP


def test_legacy_access_token_without_typ_still_works(anon_client, test_user):
    token = _token_for(test_user)
    response = anon_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


def test_token_with_non_access_typ_is_rejected(anon_client, test_user):
    token = _token_for(test_user, typ=oauth_module.STATE_TYP)
    response = anon_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_oauth_state_cannot_be_used_as_access_token(anon_client, google_creds):
    state, _ = oauth_module._sign_state("google")
    response = anon_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {state}"}
    )
    assert response.status_code == 401
