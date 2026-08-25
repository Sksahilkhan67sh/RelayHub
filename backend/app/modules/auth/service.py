from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.auth.models import (
    Membership,
    Organization,
    RefreshTokenFamily,
    Role,
    User,
)
from app.modules.auth.schemas import RegisterRequest, TokenResponse

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"org-{uuid.uuid4().hex[:8]}"


async def _unique_slug(db: AsyncSession, base_name: str) -> str:
    base = slugify(base_name)
    candidate = base
    suffix = 1
    while (await db.execute(select(Organization).where(Organization.slug == candidate))).scalar_one_or_none():
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


async def register_user(db: AsyncSession, data: RegisterRequest) -> tuple[User, Organization]:
    existing = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if existing:
        # Do not leak whether the email exists in a way that differs meaningfully from
        # other validation errors -- generic 409 with no account-enumeration detail beyond
        # "already registered" (acceptable tradeoff vs. full ambiguity, matches most SaaS UX).
        raise HTTPException(status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    org = Organization(name=data.organization_name, slug=await _unique_slug(db, data.organization_name))
    db.add(org)
    await db.flush()  # get org.id without committing

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        is_active=True,
        is_email_verified=False,
    )
    db.add(user)
    await db.flush()

    membership = Membership(user_id=user.id, organization_id=org.id, role=Role.OWNER, accepted_at=datetime.now(timezone.utc))
    db.add(membership)

    await db.commit()
    await db.refresh(user)
    await db.refresh(org)

    from app.modules.billing import service as billing_service

    await billing_service.get_or_create_subscription(db, organization_id=org.id)
    await db.refresh(org)  # plan_id/log_retention_days were just synced onto org

    return user, org


async def _get_primary_membership(db: AsyncSession, user_id: uuid.UUID) -> Membership:
    membership = (
        await db.execute(
            # tenant-scope: safe - lists every org this user belongs to (that IS the point: a user can
    # belong to multiple orgs), scoped by user_id, their own identity.
    select(Membership).where(Membership.user_id == user_id).order_by(Membership.created_at.asc())
        )
    ).scalars().first()
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="User has no organization membership")
    return membership


async def authenticate(db: AsyncSession, email: str, password: str, *, ip: str | None, user_agent: str | None) -> TokenResponse:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()

    # Constant-shape response whether or not the user exists, to reduce enumeration risk,
    # while still enforcing lockout for real accounts.
    if not user:
        # burn roughly the same time as a real bcrypt verify to reduce timing side-channel
        hash_password("dummy-password-for-timing")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    locked_until = user.locked_until
    if locked_until is not None:
        # Some DB drivers (notably SQLite) round-trip DateTime(timezone=True) columns as
        # naive datetimes. Normalize to UTC-aware before comparing to avoid a TypeError.
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status.HTTP_423_LOCKED,
                detail=f"Account temporarily locked due to repeated failed logins. Try again after {locked_until.isoformat()}",
            )

    if not verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            user.failed_login_attempts = 0
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()

    membership = await _get_primary_membership(db, user.id)
    return await _issue_token_pair(db, user, membership, ip=ip, user_agent=user_agent)


async def _issue_token_pair(
    db: AsyncSession, user: User, membership: Membership, *, ip: str | None, user_agent: str | None
) -> TokenResponse:
    access_token = create_access_token(user_id=str(user.id), org_id=str(membership.organization_id), role=membership.role)

    family_id = str(uuid.uuid4())
    refresh_token, jti = create_refresh_token(user_id=str(user.id), org_id=str(membership.organization_id), family_id=family_id)

    family = RefreshTokenFamily(
        id=uuid.UUID(family_id),
        user_id=user.id,
        organization_id=membership.organization_id,
        current_jti=jti,
        token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
        ip_address=ip,
        user_agent=user_agent,
    )
    db.add(family)
    await db.commit()

    from app.core.config import settings

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def refresh_access_token(db: AsyncSession, raw_refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(raw_refresh_token, expected_type="refresh")
    except TokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e

    family_id = payload["family_id"]
    jti = payload["jti"]
    user_id = payload["sub"]

    family = (
        # tenant-scope: safe - family_id is an unguessable UUID that IS the credential (from the refresh
        # JWT itself); org scoping is meaningless here, same as looking up a session by its own id.
        await db.execute(select(RefreshTokenFamily).where(RefreshTokenFamily.id == uuid.UUID(family_id)))
    ).scalar_one_or_none()

    if not family:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unknown refresh token family")

    if family.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token family revoked")

    presented_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()

    if family.current_jti != jti or family.token_hash != presented_hash:
        # Reuse of a rotated-out token -> likely theft. Revoke the whole family.
        family.revoked_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected; all sessions for this device family have been revoked",
        )

    user = (await db.execute(select(User).where(User.id == uuid.UUID(user_id)))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")

    membership = (
        await db.execute(
            select(Membership).where(
                Membership.user_id == user.id, Membership.organization_id == family.organization_id
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Membership no longer exists")

    # Rotate: issue new access + new refresh jti under the SAME family id
    access_token = create_access_token(user_id=str(user.id), org_id=str(membership.organization_id), role=membership.role)
    new_refresh_token, new_jti = create_refresh_token(
        user_id=str(user.id), org_id=str(membership.organization_id), family_id=str(family.id)
    )
    family.current_jti = new_jti
    family.token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
    await db.commit()

    from app.core.config import settings

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def revoke_all_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    # tenant-scope: safe - a user's own refresh-token families across every org they
    # belong to, scoped by user_id (their own identity), not another user's.
    families = (
        await db.execute(select(RefreshTokenFamily).where(RefreshTokenFamily.user_id == user_id, RefreshTokenFamily.revoked_at.is_(None)))
    ).scalars().all()
    now = datetime.now(timezone.utc)
    for f in families:
        f.revoked_at = now
    await db.commit()
