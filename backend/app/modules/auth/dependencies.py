from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.rate_limiter import RateLimiter, get_rate_limiter
from app.core.security import TokenError, decode_token
from app.db.session import get_db
from app.modules.auth.models import ROLE_HIERARCHY, Role

bearer_scheme = HTTPBearer(auto_error=True)
optional_bearer_scheme = HTTPBearer(auto_error=False)

# IP-based brute-force guard on the login endpoint. Distinct from the per-account
# lockout in auth/service.py (which triggers on repeated failures against ONE email):
# this catches an attacker rotating through many emails from a single IP, which the
# per-account mechanism can't see.
LOGIN_IP_RATE_LIMIT = 10
LOGIN_IP_RATE_WINDOW_SECONDS = 300  # 5 minutes

# Same shape, applied to /auth/forgot-password: without this, the endpoint would be a
# free email-bombing / account-enumeration-timing oracle for any IP that hammers it.
FORGOT_PASSWORD_IP_RATE_LIMIT = 5
FORGOT_PASSWORD_IP_RATE_WINDOW_SECONDS = 3600  # 1 hour


async def _enforce_rate_limit(
    request: Request,
    response: Response,
    rate_limiter: RateLimiter,
    *,
    key_prefix: str,
    header_label: str,
    limit: int,
    window_seconds: int,
    error_detail: str,
) -> None:
    ip = request.client.host if request.client else "unknown"
    result = await rate_limiter.check(f"{key_prefix}:{ip}", limit=limit, window_seconds=window_seconds)

    response.headers[f"X-RateLimit-Limit-{header_label}"] = str(result.limit)
    response.headers[f"X-RateLimit-Remaining-{header_label}"] = str(result.remaining)

    if not result.allowed:
        from datetime import datetime, timezone

        retry_after = max(1, int((result.reset_at - datetime.now(timezone.utc)).total_seconds()))
        response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_detail,
            headers=dict(response.headers),
        )


async def enforce_login_rate_limit(
    request: Request,
    response: Response,
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    await _enforce_rate_limit(
        request, response, rate_limiter,
        key_prefix="login", header_label="Login", limit=LOGIN_IP_RATE_LIMIT, window_seconds=LOGIN_IP_RATE_WINDOW_SECONDS,
        error_detail="Too many login attempts from this network, please try again later",
    )


async def enforce_forgot_password_rate_limit(
    request: Request,
    response: Response,
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    await _enforce_rate_limit(
        request, response, rate_limiter,
        key_prefix="forgot-password", header_label="Forgot-Password",
        limit=FORGOT_PASSWORD_IP_RATE_LIMIT, window_seconds=FORGOT_PASSWORD_IP_RATE_WINDOW_SECONDS,
        error_detail="Too many password reset requests from this network, please try again later",
    )


@dataclass(frozen=True)
class AuthContext:
    """
    The authenticated identity for the current request. `organization_id` here is the
    tenant boundary -- every downstream repository call MUST filter by this value.
    """

    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: Role


async def get_current_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AuthContext:
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenError as e:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail=str(e), headers={"WWW-Authenticate": "Bearer"}
        ) from e

    try:
        return AuthContext(
            user_id=uuid.UUID(payload["sub"]),
            organization_id=uuid.UUID(payload["org_id"]),
            role=Role(payload["role"]),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Malformed token claims") from e


async def get_optional_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
) -> AuthContext | None:
    """
    Like get_current_auth, but returns None instead of raising 401 when no bearer
    token is presented (or it's invalid). Used by /invitations/accept, which must
    work for a brand-new invitee with no session yet, but should also recognize an
    already-logged-in caller so their existing account can be attached directly
    instead of being told to log in first.
    """
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        return AuthContext(
            user_id=uuid.UUID(payload["sub"]),
            organization_id=uuid.UUID(payload["org_id"]),
            role=Role(payload["role"]),
        )
    except (TokenError, KeyError, ValueError):
        return None


def require_role(minimum_role: Role):
    """
    Usage: `Depends(require_role(Role.ADMIN))` -- allows ADMIN and OWNER, blocks MEMBER/VIEWER.
    """

    async def _checker(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if ROLE_HIERARCHY[auth.role] < ROLE_HIERARCHY[minimum_role]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{minimum_role.value}' or higher; you have '{auth.role.value}'",
            )
        return auth

    return _checker


async def require_platform_admin(
    auth: AuthContext = Depends(get_current_auth), db: AsyncSession = Depends(get_db)
) -> AuthContext:
    from sqlalchemy import select

    from app.modules.auth.models import User

    user = (await db.execute(select(User).where(User.id == auth.user_id))).scalar_one_or_none()
    if not user or not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Platform admin access required")
    return auth
