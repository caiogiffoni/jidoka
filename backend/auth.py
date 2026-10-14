import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

import oauth as oauth_module
from blocked_usernames import PROFANE_USERNAMES
from db import get_session
from models import (
    AuthResponse,
    User,
    UserCreate,
    UserLogin,
    UserPublic,
    password_too_long,
)
from rate_limit import limiter, login_email_allowed, record_failed_login

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_DAYS = 7

# Lazily resolve the secret so importing this module doesn't crash tests that
# haven't set the environment variable yet. Step 4 will enforce the secret on
# application startup.
def _jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY environment variable is not set")
    return secret


security = HTTPBearer()
router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str | None) -> bool:
    # Registration caps passwords at 72 bytes (bcrypt's limit; bcrypt>=5 raises
    # ValueError beyond it), so a longer one can never match - fail cleanly.
    if hashed is None or password_too_long(plain):
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "username": user.username,
        "iat": now,
        "exp": now + timedelta(days=ACCESS_TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        _jwt_secret(),
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp"]},
    )


def _to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        username=user.username,
        created_at=user.created_at,
    )


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(user=_to_public(user), token=_create_token(user))


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session),
) -> User:
    try:
        payload = _decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
        ) from exc

    try:
        user_id = uuid.UUID(payload.get("sub", ""))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token payload",
        ) from exc

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not found",
        )
    return user


@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit("5/minute")
def register(
    request: Request,
    payload: UserCreate,
    session: Session = Depends(get_session),
):
    # UserCreate already validates username/password rules, the profanity
    # blocklist, and normalizes the email; here we only check uniqueness
    # before creating the account.
    conflict = _registration_conflict(session, payload.email, payload.username)
    if conflict is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict)

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=_hash_password(payload.password),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        # A concurrent registration won the race between the check above and
        # this insert; answer with the same 409 the pre-check would have.
        session.rollback()
        conflict = _registration_conflict(session, payload.email, payload.username)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=conflict or "email or username already taken",
        ) from None
    session.refresh(user)
    return _auth_response(user)


def _registration_conflict(session: Session, email: str, username: str) -> str | None:
    # Case-insensitive so rows created before emails were normalized still
    # count as duplicates.
    existing_email = session.exec(
        select(User).where(func.lower(User.email) == email.lower())
    ).first()
    if existing_email is not None:
        return "email already registered"

    existing_username = session.exec(
        select(User).where(User.username == username)
    ).first()
    if existing_username is not None:
        return "username already taken"
    return None


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    payload: UserLogin,
    session: Session = Depends(get_session),
):
    # Per-email budget on top of the per-IP decorator limit, so one account
    # can't be brute-forced from many IPs.
    if not login_email_allowed(payload.email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many failed login attempts for this account, try again later",
        )
    # payload.email is normalized; lower() the column so existing mixed-case
    # rows still match.
    user = session.exec(
        select(User).where(func.lower(User.email) == payload.email)
    ).first()
    if user is None or not _verify_password(payload.password, user.hashed_password):
        record_failed_login(payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid email or password",
        )
    return _auth_response(user)


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return _to_public(current_user)


@router.post("/logout", status_code=204)
def logout():
    # Real logout happens in the Next.js Server Action by deleting the cookie.
    # This endpoint exists for symmetry and any future server-side revocation.
    return None


@router.get("/oauth/{provider}")
def oauth_initiate(provider: str):
    if provider not in oauth_module._PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="unknown oauth provider",
        )
    try:
        url = oauth_module.build_authorize_url(provider)  # type: ignore[arg-type]
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return RedirectResponse(url)


def _oauth_error_redirect(message: str) -> RedirectResponse:
    frontend = oauth_module._frontend_url()
    return RedirectResponse(
        f"{frontend}/oauth/callback?error={message}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str | None = None,
    state: str | None = None,
    session: Session = Depends(get_session),
):
    if provider not in oauth_module._PROVIDERS:
        return _oauth_error_redirect("unknown_provider")
    if not code or not state:
        return _oauth_error_redirect("missing_oauth_parameters")
    if not oauth_module._verify_state(state, provider):  # type: ignore[arg-type]
        return _oauth_error_redirect("invalid_state")

    try:
        info = await oauth_module.fetch_userinfo(provider, code)  # type: ignore[arg-type]
    except RuntimeError as exc:
        return _oauth_error_redirect(str(exc).replace(" ", "_"))
    except httpx.HTTPError as exc:
        return _oauth_error_redirect("provider_request_failed")

    user = oauth_module.get_or_create_oauth_user(
        session, provider, info  # type: ignore[arg-type]
    )
    token = _create_token(user)
    frontend = oauth_module._frontend_url()
    return RedirectResponse(
        f"{frontend}/oauth/callback?token={token}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
