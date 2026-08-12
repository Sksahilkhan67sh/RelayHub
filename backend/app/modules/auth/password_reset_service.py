from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.notification_client import NotificationDispatcher
from app.core.config import settings
from app.core.security import generate_secure_token, hash_password
from app.modules.audit import service as audit_service
from app.modules.audit.models import AuditAction
from app.modules.auth import service as auth_service
from app.modules.auth.models import PasswordResetToken, User

GENERIC_FORGOT_PASSWORD_MESSAGE = "If an account exists for that email, a password reset link has been sent."
INVALID_OR_EXPIRED_TOKEN_MESSAGE = "Invalid or expired reset token"


async def request_password_reset(
    db: AsyncSession,
    *,
    email: str,
    notification_dispatcher: NotificationDispatcher,
    ip_address: str | None,
) -> None:
    """
    Always completes the same way whether or not `email` belongs to a real account --
    the response the caller sends back never differs, so this function never raises
    for "not found". Every attempt is logged regardless of outcome (spec: "Log every
    request").
    """
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()

    await audit_service.record(
        db,
        organization_id=None,
        actor_user_id=user.id if user else None,
        action=AuditAction.PASSWORD_RESET_REQUESTED,
        resource_type="user",
        resource_id=str(user.id) if user else None,
        metadata={"email": email},
        ip_address=ip_address,
    )

    if not user or not user.is_active:
        await db.commit()
        return

    # Invalidate previous active reset tokens before issuing a new one, so only the
    # most recently requested link can ever be used.
    active_tokens = (
        await db.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        )
    ).scalars().all()
    now = datetime.now(timezone.utc)
    for token_row in active_tokens:
        token_row.used_at = now

    raw_token, token_hash = generate_secure_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            hashed_token=token_hash,
            expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
    )
    await db.commit()

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    await notification_dispatcher.send(
        channel="email",
        config={"to_address": user.email},
        subject="Reset your RelayHub password",
        message=(
            "We received a request to reset your RelayHub password. Click the link below to "
            f"choose a new one -- it expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes "
            "and can only be used once.\n\n"
            f"{reset_link}\n\n"
            "If you didn't request this, you can safely ignore this email; your password will not change."
        ),
    )


async def confirm_password_reset(
    db: AsyncSession,
    *,
    raw_token: str,
    new_password: str,
    ip_address: str | None,
) -> None:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    reset_token = (
        await db.execute(select(PasswordResetToken).where(PasswordResetToken.hashed_token == token_hash))
    ).scalar_one_or_none()

    if not reset_token or not reset_token.is_valid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=INVALID_OR_EXPIRED_TOKEN_MESSAGE)

    user = (await db.execute(select(User).where(User.id == reset_token.user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=INVALID_OR_EXPIRED_TOKEN_MESSAGE)

    now = datetime.now(timezone.utc)

    user.hashed_password = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None

    reset_token.used_at = now

    # Defense in depth: invalidate any other still-active tokens for this user too,
    # not just the one that was used.
    other_active = (
        await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.id != reset_token.id,
                PasswordResetToken.used_at.is_(None),
            )
        )
    ).scalars().all()
    for token_row in other_active:
        token_row.used_at = now

    await audit_service.record(
        db,
        organization_id=None,
        actor_user_id=user.id,
        action=AuditAction.PASSWORD_RESET_COMPLETED,
        resource_type="user",
        resource_id=str(user.id),
        metadata={},
        ip_address=ip_address,
    )
    await db.commit()

    # Force re-login everywhere: revoke every refresh-token family for this user
    # (reuses the same helper `logout` uses).
    await auth_service.revoke_all_sessions(db, user.id)
