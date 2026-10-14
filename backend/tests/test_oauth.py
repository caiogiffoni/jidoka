import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
import pytest
from sqlmodel import Session, select

import auth
import oauth as oauth_module
from models import OAuthExchangeCode, User


@pytest.fixture()
def google_creds(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-client-secret")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "github-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "github-client-secret")


def test_sign_and_verify_state(google_creds):
    state, nonce = oauth_module._sign_state("google")
    assert oauth_module._verify_state(state, "google", nonce) is True


def test_state_does_not_contain_raw_nonce(google_creds):
    state, nonce = oauth_module._sign_state("google")
    payload = jwt.decode(state, options={"verify_signature": False})
    assert nonce not in state
    assert nonce not in payload.values()
    assert payload["typ"] == oauth_module.STATE_TYP


def test_verify_state_rejects_missing_cookie_nonce(google_creds):
    state, _ = oauth_module._sign_state("google")
    assert oauth_module._verify_state(state, "google", None) is False
    assert oauth_module._verify_state(state, "google", "") is False


def test_verify_state_rejects_mismatched_cookie_nonce(google_creds):
    state, _ = oauth_module._sign_state("google")
    _, other_nonce = oauth_module._sign_state("google")
    assert oauth_module._verify_state(state, "google", other_nonce) is False


def test_verify_state_rejects_wrong_provider(google_creds):
    state, nonce = oauth_module._sign_state("google")
    assert oauth_module._verify_state(state, "github", nonce) is False


def test_verify_state_rejects_token_without_state_typ(google_creds):
    """An access token (or any other JWT from the same key) is not a state."""
    nonce = "n"
    forged = jwt.encode(
        {
            "provider": "google",
            "nonce_hash": oauth_module._hash(nonce),
            "typ": auth.ACCESS_TOKEN_TYP,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        auth._jwt_secret(),
        algorithm=auth.JWT_ALGORITHM,
    )
    assert oauth_module._verify_state(forged, "google", nonce) is False


def test_verify_state_rejects_invalid_signature(google_creds):
    state = jwt.encode(
        {
            "typ": oauth_module.STATE_TYP,
            "provider": "google",
            "nonce_hash": oauth_module._hash("x"),
        },
        "wrong-secret-that-is-long-enough-for-hs256-keys",
        algorithm=auth.JWT_ALGORITHM,
    )
    assert oauth_module._verify_state(state, "google", "x") is False


def test_verify_state_rejects_expired_token(google_creds):
    payload = {
        "typ": oauth_module.STATE_TYP,
        "provider": "google",
        "nonce_hash": oauth_module._hash("x"),
        "iat": datetime.now(timezone.utc) - timedelta(hours=1),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    state = jwt.encode(payload, auth._jwt_secret(), algorithm=auth.JWT_ALGORITHM)
    assert oauth_module._verify_state(state, "google", "x") is False


def test_state_token_is_not_accepted_as_access_token(google_creds):
    state, _ = oauth_module._sign_state("google")
    with pytest.raises(jwt.PyJWTError):
        auth._decode_token(state)


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


def test_get_or_create_oauth_user_refuses_to_link_password_account(session: Session):
    """Pre-registration takeover: never attach a provider login to a password
    account, even when the provider says the email is verified."""
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
    with pytest.raises(oauth_module.OAuthError) as exc_info:
        oauth_module.get_or_create_oauth_user(session, "github", info)
    assert exc_info.value.code == "account_exists_password"

    session.refresh(existing)
    assert existing.oauth_provider is None
    assert existing.oauth_provider_id is None


def test_get_or_create_oauth_user_matches_email_case_insensitively(session: Session):
    existing = User(
        email="Mixed.Case@Example.com",
        username="mixeduser",
        hashed_password="hashed",
    )
    session.add(existing)
    session.commit()

    info = oauth_module.OAuthUserInfo(
        provider_id="google-mixed",
        email="mixed.case@EXAMPLE.COM",
        email_verified=True,
        username_base="mixed",
    )
    with pytest.raises(oauth_module.OAuthError) as exc_info:
        oauth_module.get_or_create_oauth_user(session, "google", info)
    assert exc_info.value.code == "account_exists_password"


def test_get_or_create_oauth_user_refuses_to_link_other_provider_account(
    session: Session,
):
    existing = User(
        email="gh@example.com",
        username="ghonly",
        oauth_provider="github",
        oauth_provider_id="github-9",
    )
    session.add(existing)
    session.commit()

    info = oauth_module.OAuthUserInfo(
        provider_id="google-9",
        email="gh@example.com",
        email_verified=True,
        username_base="ghonly",
    )
    with pytest.raises(oauth_module.OAuthError) as exc_info:
        oauth_module.get_or_create_oauth_user(session, "google", info)
    assert exc_info.value.code == "account_exists_oauth"

    session.refresh(existing)
    assert existing.oauth_provider == "github"
    assert existing.oauth_provider_id == "github-9"


def test_get_or_create_oauth_user_refuses_unverified_email(session: Session):
    info = oauth_module.OAuthUserInfo(
        provider_id="google-2",
        email="unverified@example.com",
        email_verified=False,
        username_base="unverified",
    )
    with pytest.raises(oauth_module.OAuthError) as exc_info:
        oauth_module.get_or_create_oauth_user(session, "google", info)
    assert exc_info.value.code == "email_unverified"


def test_get_or_create_oauth_user_lowercases_new_email(session: Session):
    info = oauth_module.OAuthUserInfo(
        provider_id="google-upper",
        email="Upper@Example.com",
        email_verified=True,
        username_base="Upper",
    )
    user = oauth_module.get_or_create_oauth_user(session, "google", info)
    assert user.email == "upper@example.com"


def test_exchange_code_is_single_use(session: Session, test_user):
    code = oauth_module.issue_exchange_code(session, test_user)

    user = oauth_module.redeem_exchange_code(session, code)
    assert user is not None and user.id == test_user.id

    assert oauth_module.redeem_exchange_code(session, code) is None


def test_exchange_code_stores_only_a_hash(session: Session, test_user):
    code = oauth_module.issue_exchange_code(session, test_user)
    rows = session.exec(
        select(OAuthExchangeCode).where(OAuthExchangeCode.user_id == test_user.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].code_hash != code
    assert rows[0].code_hash == oauth_module._hash(code)


def test_exchange_code_expires(session: Session, test_user):
    code = oauth_module.issue_exchange_code(session, test_user)
    row = session.exec(
        select(OAuthExchangeCode).where(
            OAuthExchangeCode.code_hash == oauth_module._hash(code)
        )
    ).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.add(row)
    session.commit()

    assert oauth_module.redeem_exchange_code(session, code) is None


def test_exchange_code_ttl_is_at_most_60_seconds(session: Session, test_user):
    code = oauth_module.issue_exchange_code(session, test_user)
    row = session.exec(
        select(OAuthExchangeCode).where(
            OAuthExchangeCode.code_hash == oauth_module._hash(code)
        )
    ).one()
    assert row.expires_at - datetime.now(timezone.utc) <= timedelta(seconds=60)


def test_redeem_rejects_unknown_code(session: Session):
    assert oauth_module.redeem_exchange_code(session, "nope") is None
    assert oauth_module.redeem_exchange_code(session, "") is None


def test_issue_exchange_code_cleans_up_stale_rows(session: Session, test_user):
    stale = oauth_module.issue_exchange_code(session, test_user)
    used = oauth_module.issue_exchange_code(session, test_user)
    oauth_module.redeem_exchange_code(session, used)
    row = session.exec(
        select(OAuthExchangeCode).where(
            OAuthExchangeCode.code_hash == oauth_module._hash(stale)
        )
    ).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.add(row)
    session.commit()

    oauth_module.issue_exchange_code(session, test_user)

    hashes = set(
        session.exec(
            select(OAuthExchangeCode.code_hash).where(
                OAuthExchangeCode.user_id == test_user.id
            )
        ).all()
    )
    assert oauth_module._hash(stale) not in hashes
    assert oauth_module._hash(used) not in hashes
    assert len(hashes) == 1


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
    url, nonce = oauth_module.build_authorize_url("google")
    assert nonce and nonce not in url

    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "client_id=google-client-id" in url
    assert "response_type=code" in url
    assert "state=" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Foauth%2Fgoogle%2Fcallback" in url
