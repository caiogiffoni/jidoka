import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
import pytest
from sqlmodel import Session, select

import auth
import oauth as oauth_module
from models import User


@pytest.fixture()
def google_creds(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "github-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "github-client-secret")


def test_sign_and_verify_state(google_creds):
    state = oauth_module._sign_state("google")
    assert oauth_module._verify_state(state, "google") is True


def test_verify_state_rejects_wrong_provider(google_creds):
    state = oauth_module._sign_state("google")
    assert oauth_module._verify_state(state, "github") is False


def test_verify_state_rejects_invalid_signature(google_creds):
    state = jwt.encode(
        {"provider": "google", "nonce": "x"},
        "wrong-secret",
        algorithm=auth.JWT_ALGORITHM,
    )
    assert oauth_module._verify_state(state, "google") is False


def test_verify_state_rejects_expired_token(google_creds):
    payload = {
        "provider": "google",
        "nonce": "x",
        "iat": datetime.now(timezone.utc) - timedelta(hours=1),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    state = jwt.encode(payload, auth._jwt_secret(), algorithm=auth.JWT_ALGORITHM)
    assert oauth_module._verify_state(state, "google") is False


def test_client_credentials_raises_when_unconfigured(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        oauth_module._client_credentials("google")


def test_normalize_username_cleans_special_characters():
    assert oauth_module._normalize_username("John Doe!") == "JohnDoe"
    assert oauth_module._normalize_username("123starts-with-number") == "user"
    assert oauth_module._normalize_username("ab") == "user"
    assert oauth_module._normalize_username("valid_user-name") == "valid_user-name"


def test_resolve_username_avoids_collisions(session: Session):
    session.add(User(email="a@example.com", username="johndoe"))
    session.commit()

    assert oauth_module._resolve_username(session, "johndoe") == "johndoe1"

    session.add(User(email="b@example.com", username="johndoe1"))
    session.commit()

    assert oauth_module._resolve_username(session, "johndoe") == "johndoe2"


def test_resolve_username_truncates_long_base_before_appending_suffix(session: Session):
    long_base = "a" * 30
    session.add(User(email="a@example.com", username=long_base))
    session.commit()

    resolved = oauth_module._resolve_username(session, long_base)
    assert len(resolved) <= 30
    assert resolved.startswith("a" * 29)


def test_get_or_create_oauth_user_creates_new_user(session: Session):
    info = oauth_module.OAuthUserInfo(
        provider_id="google-1",
        email="new@example.com",
        email_verified=True,
        username_base="New User",
    )
    user = oauth_module.get_or_create_oauth_user(session, "google", info)

    assert user.email == "new@example.com"
    assert user.username == "NewUser"
    assert user.hashed_password is None
    assert user.oauth_provider == "google"
    assert user.oauth_provider_id == "google-1"


def test_get_or_create_oauth_user_links_verified_email(session: Session):
    existing = User(
        email="link@example.com",
        username="linkuser",
        hashed_password="hashed",
    )
    session.add(existing)
    session.commit()

    info = oauth_module.OAuthUserInfo(
        provider_id="github-1",
        email="link@example.com",
        email_verified=True,
        username_base="linkuser",
    )
    user = oauth_module.get_or_create_oauth_user(session, "github", info)

    assert user.id == existing.id
    assert user.oauth_provider == "github"
    assert user.oauth_provider_id == "github-1"


def test_get_or_create_oauth_user_does_not_link_unverified_email(session: Session):
    existing = User(
        email="nolink@example.com",
        username="nolinkuser",
        hashed_password="hashed",
    )
    session.add(existing)
    session.commit()

    info = oauth_module.OAuthUserInfo(
        provider_id="google-2",
        email="nolink@example.com",
        email_verified=False,
        username_base="nolinkuser",
    )
    with pytest.raises(RuntimeError, match="account with this email already exists"):
        oauth_module.get_or_create_oauth_user(session, "google", info)


def test_get_or_create_oauth_user_returns_existing_oauth_user(session: Session):
    existing = User(
        email="existing@example.com",
        username="existinguser",
        oauth_provider="google",
        oauth_provider_id="google-3",
    )
    session.add(existing)
    session.commit()

    info = oauth_module.OAuthUserInfo(
        provider_id="google-3",
        email="changed@example.com",
        email_verified=True,
        username_base="existinguser",
    )
    user = oauth_module.get_or_create_oauth_user(session, "google", info)

    assert user.id == existing.id


def test_get_or_create_oauth_user_uses_email_prefix_when_name_invalid(session: Session):
    info = oauth_module.OAuthUserInfo(
        provider_id="google-4",
        email="alex@example.com",
        email_verified=True,
        username_base="!!!",
    )
    user = oauth_module.get_or_create_oauth_user(session, "google", info)

    assert user.username == "alex"


@pytest.fixture()
def fake_async_client(monkeypatch):
    """Replace httpx.AsyncClient with a configurable async mock."""

    class FakeResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json = json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError("HTTP error")

        def json(self):
            return self._json

    class FakeClient:
        def __init__(self, responses):
            self.responses = responses
            self.calls = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            self.calls.append(("post", url, kwargs))
            return self.responses.pop(0)

        async def get(self, url, **kwargs):
            self.calls.append(("get", url, kwargs))
            return self.responses.pop(0)

    def make_client(*args, **kwargs):
        return FakeClient(make_client.responses)

    make_client.responses = []
    make_client.FakeResponse = FakeResponse
    monkeypatch.setattr(oauth_module.httpx, "AsyncClient", make_client)
    return make_client


@pytest.mark.anyio
async def test_fetch_google_userinfo(fake_async_client, google_creds):
    fake_async_client.responses = [
        fake_async_client.FakeResponse(200, {"access_token": "tok"}),
        fake_async_client.FakeResponse(
            200,
            {
                "id": "g-id",
                "email": "google@example.com",
                "verified_email": True,
                "name": "Google User",
            },
        ),
    ]

    info = await oauth_module.fetch_userinfo("google", "code")

    assert info.provider_id == "g-id"
    assert info.email == "google@example.com"
    assert info.email_verified is True
    assert info.username_base == "Google User"


@pytest.mark.anyio
async def test_fetch_github_userinfo(fake_async_client, google_creds):
    fake_async_client.responses = [
        fake_async_client.FakeResponse(200, {"access_token": "tok"}),
        fake_async_client.FakeResponse(200, {"id": 12345, "login": "ghuser"}),
        fake_async_client.FakeResponse(
            200,
            [
                {"email": "primary@example.com", "primary": True, "verified": True},
                {"email": "other@example.com", "primary": False, "verified": True},
            ],
        ),
    ]

    info = await oauth_module.fetch_userinfo("github", "code")

    assert info.provider_id == "12345"
    assert info.email == "primary@example.com"
    assert info.email_verified is True
    assert info.username_base == "ghuser"


@pytest.mark.anyio
async def test_fetch_github_userinfo_prefers_verified_primary_email(fake_async_client, google_creds):
    fake_async_client.responses = [
        fake_async_client.FakeResponse(200, {"access_token": "tok"}),
        fake_async_client.FakeResponse(200, {"id": 1, "login": "user"}),
        fake_async_client.FakeResponse(
            200,
            [
                {"email": "unverified@example.com", "primary": True, "verified": False},
                {"email": "verified@example.com", "primary": False, "verified": True},
            ],
        ),
    ]

    info = await oauth_module.fetch_userinfo("github", "code")

    assert info.email == "verified@example.com"
    assert info.email_verified is True


@pytest.mark.anyio
async def test_fetch_userinfo_raises_when_access_token_missing(fake_async_client, google_creds):
    fake_async_client.responses = [
        fake_async_client.FakeResponse(200, {"no_access_token": True}),
    ]

    with pytest.raises(RuntimeError, match="access_token"):
        await oauth_module.fetch_userinfo("google", "code")


def test_build_authorize_url_contains_expected_params(google_creds):
    url = oauth_module.build_authorize_url("google")

    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "client_id=google-client-id" in url
    assert "response_type=code" in url
    assert "state=" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Foauth%2Fgoogle%2Fcallback" in url
