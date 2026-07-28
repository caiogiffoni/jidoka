import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlmodel import Session, select

from blocked_usernames import PROFANE_USERNAMES
from db import get_session
from models import AuthResponse, User, UserCreate, UserLogin, UserPublic

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


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


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
def register(payload: UserCreate, session: Session = Depends(get_session)):
    # UserCreate already validates username/password rules and the profanity
    # blocklist; here we only check uniqueness before creating the account.
    existing_email = session.exec(
        select(User).where(User.email == payload.email)
    ).first()
    if existing_email is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already registered",
        )

    existing_username = session.exec(
        select(User).where(User.username == payload.username)
    ).first()
    if existing_username is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username already taken",
        )

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=_hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLogin, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if user is None or not _verify_password(payload.password, user.hashed_password):
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
