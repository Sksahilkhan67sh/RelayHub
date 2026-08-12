"""
Security primitives for RelayHub.

Design notes:
- Access tokens: short-lived JWT (default 15m), stateless, carry org_id + role + user_id.
- Refresh tokens: long-lived, stored server-side (hashed) as a *token family* so that
  reuse-detection is possible (rotating refresh tokens: if an old refresh token is
  replayed after rotation, the entire family is revoked -> mitigates token theft).
- Passwords: bcrypt via passlib, cost factor 12.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

TokenType = Literal["access", "refresh"]


class TokenError(Exception):
    """Raised for any invalid/expired/tampered token."""


def hash_password(plain_password: str) -> str:
    if len(plain_password) < 8:
        raise ValueError("Password must be at least 8 characters")
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(*, user_id: str, org_id: str, role: str) -> str:
    payload: dict[str, Any] = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "type": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(*, user_id: str, org_id: str, family_id: str) -> tuple[str, str]:
    """
    Returns (raw_token, jti). The raw token is returned to the client once; only a hash
    of it is persisted (see auth/service.py) so a DB leak doesn't leak usable tokens.
    """
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": user_id,
        "org_id": org_id,
        "type": "refresh",
        "family_id": family_id,
        "jti": jti,
        "iat": _now(),
        "exp": _now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise TokenError("Token expired") from e
    except jwt.InvalidTokenError as e:
        raise TokenError("Invalid token") from e

    if payload.get("type") != expected_type:
        raise TokenError(f"Expected token type '{expected_type}', got '{payload.get('type')}'")
    return payload


def generate_api_key(*, live: bool) -> tuple[str, str, str]:
    """
    Generates a RelayHub API key.
    Returns (full_key_to_show_once, key_prefix_for_display, sha256_hash_to_store).
    Format: rh_live_<32 random url-safe chars> or rh_test_<...>
    """
    import hashlib

    env_tag = "live" if live else "test"
    secret_part = secrets.token_urlsafe(32)
    full_key = f"rh_{env_tag}_{secret_part}"
    prefix = full_key[:12]  # e.g. rh_live_ab12 - safe to display
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, key_hash


def hash_api_key(raw_key: str) -> str:
    import hashlib

    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_secure_token() -> tuple[str, str]:
    """
    General-purpose one-time-use token generator, for flows like password reset and
    org invitations (see auth/password_reset_service.py, auth/invitation_service.py).

    Returns (raw_token, sha256_hash_to_store). Same "never persist the raw secret"
    pattern as generate_api_key/hash_api_key above -- the raw token is handed to the
    caller once (to embed in an emailed link) and only the hash is ever written to
    the database, so a DB leak alone can't be used to complete the flow.
    """
    import hashlib

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash
