import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx
import jwt
from sqlmodel import Session, select

import auth
from models import User

OAuthProvider = Literal["google", "github"]
STATE_TTL_MINUTES = 5


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


def _sign_state(provider: OAuthProvider) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "provider": provider,
        "nonce": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + timedelta(minutes=STATE_TTL_MINUTES),
    }
    return jwt.encode(payload, auth._jwt_secret(), algorithm=auth.JWT_ALGORITHM)


def _verify_state(state: str, provider: OAuthProvider) -> bool:
    try:
        payload = jwt.decode(
            state,
            auth._jwt_secret(),
            algorithms=[auth.JWT_ALGORITHM],
            options={"require": ["exp"]},
        )
    except jwt.PyJWTError:
        return False
    return payload.get("provider") == provider


def build_authorize_url(provider: OAuthProvider) -> str:
    client_id, _ = _client_credentials(provider)
    config = _PROVIDERS[provider]
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri(provider),
        "response_type": "code",
        "scope": config["scope"],
        "state": _sign_state(provider),
        "access_type": "online",
    }
    # httpx handles URL encoding; keeping the call synchronous because it only
    # builds a URL, no I/O.
    return str(httpx.URL(config["authorize_url"], params=params))


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

    primary_email = next(
        (e for e in emails if e.get("primary") and e.get("verified")),
        None,
    )
    fallback_email = next((e for e in emails if e.get("primary")), None)
    chosen = primary_email or fallback_email
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

    # Link to an existing password user only when the email is verified.
    if info.email_verified:
        linked = session.exec(select(User).where(User.email == info.email)).first()
        if linked is not None:
            linked.oauth_provider = provider
            linked.oauth_provider_id = info.provider_id
            session.add(linked)
            session.commit()
            session.refresh(linked)
            return linked

    user = User(
        email=info.email,
        username=_resolve_username(session, info.username_base),
        oauth_provider=provider,
        oauth_provider_id=info.provider_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
