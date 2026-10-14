import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx
import jwt
from sqlalchemy import delete, func, or_, update
from sqlmodel import Session, SQLModel, select

import auth
from models import OAuthExchangeCode, User

OAuthProvider = Literal["google", "github"]
STATE_TTL_MINUTES = 5
STATE_TYP = "oauth_state"
# The state nonce lives in this cookie so a state value is only valid in the
# browser that started the flow (login-CSRF protection). Scoped to the OAuth
# routes so it is never sent anywhere else.
STATE_COOKIE = "jidoka_oauth_state"
STATE_COOKIE_PATH = "/auth/oauth"
# One-time code handed to the frontend instead of the session JWT.
EXCHANGE_CODE_TTL_SECONDS = 60


class OAuthExchangeRequest(SQLModel):
    code: str


class OAuthError(Exception):
    """An OAuth failure with a fixed, user-facing error code.

    The code is the only thing that reaches the browser (as ``?error=``), so
    it must always be one of a known set - never free text.
    """

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class OAuthUserInfo:
    provider_id: str
    email: str
    email_verified: bool
    username_base: str


_PROVIDERS = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scope": "openid email profile",
    },
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "emails_url": "https://api.github.com/user/emails",
        "scope": "user:email read:user",
    },
}

_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{2,29}$")


def _client_credentials(provider: OAuthProvider) -> tuple[str, str]:
    client_id = os.environ.get(f"{provider.upper()}_CLIENT_ID", "").strip()
    client_secret = os.environ.get(f"{provider.upper()}_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(f"{provider} OAuth credentials are not configured")
    return client_id, client_secret


def _backend_url() -> str:
    return os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")


def _frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")


def _redirect_uri(provider: OAuthProvider) -> str:
    return f"{_backend_url()}/auth/oauth/{provider}/callback"


def state_cookie_secure() -> bool:
    """Mark the state cookie Secure whenever the backend is served over HTTPS."""
    return _backend_url().startswith("https://")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sign_state(provider: OAuthProvider) -> tuple[str, str]:
    """Return ``(state, nonce)``.

    The nonce goes into the browser's httpOnly state cookie; the state only
    carries its hash, so a state leaked via the provider URL or logs can't be
    turned into a matching cookie.
    """
    now = datetime.now(timezone.utc)
    nonce = secrets.token_urlsafe(32)
    payload = {
        "typ": STATE_TYP,
        "provider": provider,
        "nonce_hash": _hash(nonce),
        "iat": now,
        "exp": now + timedelta(minutes=STATE_TTL_MINUTES),
    }
    state = jwt.encode(payload, auth._jwt_secret(), algorithm=auth.JWT_ALGORITHM)
    return state, nonce


def _verify_state(state: str, provider: OAuthProvider, cookie_nonce: str | None) -> bool:
    if not cookie_nonce:
        return False
    try:
        payload = jwt.decode(
            state,
            auth._jwt_secret(),
            algorithms=[auth.JWT_ALGORITHM],
            options={"require": ["exp"]},
        )
    except jwt.PyJWTError:
        return False
    if payload.get("typ") != STATE_TYP or payload.get("provider") != provider:
        return False
    expected = payload.get("nonce_hash")
    if not isinstance(expected, str):
        return False
    return hmac.compare_digest(expected, _hash(cookie_nonce))


def build_authorize_url(provider: OAuthProvider) -> tuple[str, str]:
    """Return ``(authorize_url, nonce)``; the caller stores the nonce in the
    state cookie."""
    client_id, _ = _client_credentials(provider)
    config = _PROVIDERS[provider]
    state, nonce = _sign_state(provider)
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri(provider),
        "response_type": "code",
        "scope": config["scope"],
        "state": state,
        "access_type": "online",
    }
    # httpx handles URL encoding; keeping the call synchronous because it only
    # builds a URL, no I/O.
    return str(httpx.URL(config["authorize_url"], params=params)), nonce


async def _exchange_code(provider: OAuthProvider, code: str) -> str:
    client_id, client_secret = _client_credentials(provider)
    config = _PROVIDERS[provider]
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _redirect_uri(provider),
        "client_id": client_id,
        "client_secret": client_secret,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            config["token_url"],
            data=data,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()

    access_token = payload.get("access_token")
    if not access_token or not isinstance(access_token, str):
        raise RuntimeError(f"{provider} token response did not include access_token")
    return access_token


async def _fetch_google_userinfo(access_token: str) -> OAuthUserInfo:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            _PROVIDERS["google"]["userinfo_url"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        data = response.json()

    return OAuthUserInfo(
        provider_id=str(data["id"]),
        email=data["email"],
        email_verified=bool(data.get("verified_email", False)),
        username_base=(data.get("name") or data["email"].split("@")[0]),
    )


async def _fetch_github_userinfo(access_token: str) -> OAuthUserInfo:
    config = _PROVIDERS["github"]
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            config["userinfo_url"],
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        user_response.raise_for_status()
        user = user_response.json()

        emails_response = await client.get(
            config["emails_url"],
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        emails_response.raise_for_status()
        emails = emails_response.json()

    # Prefer a verified email; among verified emails prefer the primary one.
    # Fall back to the primary email even if unverified, but fail if none exist.
    verified_primary = next(
        (e for e in emails if e.get("primary") and e.get("verified")),
        None,
    )
    any_verified = next((e for e in emails if e.get("verified")), None)
    primary = next((e for e in emails if e.get("primary")), None)
    chosen = verified_primary or any_verified or primary
    if chosen is None:
        raise RuntimeError("GitHub did not return a usable email address")

    return OAuthUserInfo(
        provider_id=str(user["id"]),
        email=chosen["email"],
        email_verified=bool(chosen.get("verified", False)),
        username_base=user.get("login") or chosen["email"].split("@")[0],
    )


async def fetch_userinfo(provider: OAuthProvider, code: str) -> OAuthUserInfo:
    access_token = await _exchange_code(provider, code)
    if provider == "google":
        return await _fetch_google_userinfo(access_token)
    return await _fetch_github_userinfo(access_token)


def _normalize_username(base: str) -> str:
    """Turn an arbitrary display name/email prefix into a valid username."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", base).strip("-_")[:30]
    if _USERNAME_RE.match(cleaned):
        return cleaned
    # Fall back to a safe generic base; uniqueness is resolved later.
    return "user"


def _resolve_username(session: Session, base: str) -> str:
    candidate = _normalize_username(base)
    if session.exec(select(User).where(User.username == candidate)).first() is None:
        return candidate

    for n in range(1, 10000):
        suffix = str(n)
        adjusted = candidate[: 30 - len(suffix)] + suffix
        if (
            session.exec(select(User).where(User.username == adjusted)).first()
            is None
        ):
            return adjusted

    raise RuntimeError("could not generate a unique username")


def get_or_create_oauth_user(
    session: Session, provider: OAuthProvider, info: OAuthUserInfo
) -> User:
    # Existing OAuth identity takes precedence.
    existing = session.exec(
        select(User).where(
            User.oauth_provider == provider,
            User.oauth_provider_id == info.provider_id,
        )
    ).first()
    if existing is not None:
        return existing

    email = info.email.strip().lower()

    # Never auto-link to an existing account by email. Password signup does
    # not verify email ownership, so linking would hand the real owner's
    # provider login to whoever pre-registered that address. Accounts created
    # by another provider are refused too: we don't record whether that
    # provider verified the email, and the User row holds only one identity,
    # so linking would also silently drop the original login method.
    existing_by_email = session.exec(
        select(User).where(func.lower(User.email) == email)
    ).first()
    if existing_by_email is not None:
        if existing_by_email.hashed_password is not None:
            raise OAuthError("account_exists_password")
        raise OAuthError("account_exists_oauth")

    # Only provider-verified emails may claim an address for a new account.
    if not info.email_verified:
        raise OAuthError("email_unverified")

    username_base = info.username_base
    if _normalize_username(username_base) == "user":
        username_base = email.split("@")[0]

    user = User(
        email=email,
        username=_resolve_username(session, username_base),
        oauth_provider=provider,
        oauth_provider_id=info.provider_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def issue_exchange_code(session: Session, user: User) -> str:
    """Create a short-lived, single-use code the frontend trades for a JWT.

    Only the code's hash is stored. Expired and consumed rows are cleaned up
    opportunistically here so the table never grows unbounded.
    """
    now = datetime.now(timezone.utc)
    session.execute(
        delete(OAuthExchangeCode).where(
            or_(
                OAuthExchangeCode.expires_at < now,
                OAuthExchangeCode.consumed.is_(True),
            )
        )
    )
    code = secrets.token_urlsafe(32)
    session.add(
        OAuthExchangeCode(
            code_hash=_hash(code),
            user_id=user.id,
            expires_at=now + timedelta(seconds=EXCHANGE_CODE_TTL_SECONDS),
        )
    )
    session.commit()
    return code


def redeem_exchange_code(session: Session, code: str) -> User | None:
    """Consume a code atomically; returns None if unknown, used, or expired."""
    if not code:
        return None
    now = datetime.now(timezone.utc)
    # A single conditional UPDATE makes redemption race-safe: two concurrent
    # requests with the same code can't both flip consumed from false.
    user_id = session.execute(
        update(OAuthExchangeCode)
        .where(
            OAuthExchangeCode.code_hash == _hash(code),
            OAuthExchangeCode.consumed.is_(False),
            OAuthExchangeCode.expires_at > now,
        )
        .values(consumed=True)
        .returning(OAuthExchangeCode.user_id)
    ).scalar_one_or_none()
    session.commit()
    if user_id is None:
        return None
    return session.get(User, user_id)
