from __future__ import annotations

import hashlib
import uuid
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
from app.modules.auth.dependencies import AuthContext
from app.modules.auth.models import Invitation, Membership, Organization, Role, User
from app.modules.auth.schemas import TokenResponse
from app.modules.notifications import service as notifications_service

_STATUS_MESSAGES = {
    "accepted": "This invitation has already been accepted",
    "revoked": "This invitation has been revoked",
    "expired": "This invitation has expired",
}


async def create_invitation(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    email: str,
    role: Role,
    actor_user_id: uuid.UUID,
    notification_dispatcher: NotificationDispatcher,
    ip_address: str | None,
) -> Invitation:
    existing_member = (
        await db.execute(
            select(Membership)
            .join(User, User.id == Membership.user_id)
            .where(Membership.organization_id == organization_id, User.email == email)
        )
    ).scalar_one_or_none()
    if existing_member:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"'{email}' is already a member of this organization")

    duplicate = (
        await db.execute(
            select(Invitation).where(Invitation.organization_id == organization_id, Invitation.email == email)
        )
    ).scalars().all()
    if any(inv.status == "pending" for inv in duplicate):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"An invitation is already pending for '{email}'")

    org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalar_one()

    raw_token, token_hash = generate_secure_token()
    invitation = Invitation(
        organization_id=organization_id,
        email=email,
        role=role.value,
        invited_by_user_id=actor_user_id,
        hashed_token=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.INVITATION_TOKEN_EXPIRE_DAYS),
    )
    db.add(invitation)
    await db.flush()

    await audit_service.record(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction.INVITATION_CREATED,
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"email": email, "role": role.value},
        ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(invitation)

    accept_link = f"{settings.FRONTEND_URL}/accept-invitation?token={raw_token}"
    await notification_dispatcher.send(
        channel="email",
        config={"to_address": email},
        subject=f"You've been invited to join {org.name} on RelayHub",
        message=(
            f"You've been invited to join {org.name} on RelayHub as {role.value}. "
            f"This invitation expires in {settings.INVITATION_TOKEN_EXPIRE_DAYS} days.\n\n"
            f"{accept_link}"
        ),
    )

    return invitation


async def get_invitation_by_token(db: AsyncSession, *, raw_token: str) -> tuple[Invitation, Organization]:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    row = (
        await db.execute(
            select(Invitation, Organization)
            .join(Organization, Organization.id == Invitation.organization_id)
            .where(Invitation.hashed_token == token_hash)
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    invitation, org = row
    return invitation, org


async def accept_invitation(
    db: AsyncSession,
    *,
    raw_token: str,
    full_name: str | None,
    password: str | None,
    current_auth: AuthContext | None,
    ip_address: str | None,
) -> TokenResponse:
    invitation, _org = await get_invitation_by_token(db, raw_token=raw_token)

    if invitation.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_STATUS_MESSAGES.get(invitation.status, "This invitation is no longer valid"))

    existing_user = (await db.execute(select(User).where(User.email == invitation.email))).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if existing_user:
        # An account already exists for this email. Only attach the membership if the
        # caller has proven they own that account (a valid access token for that same
        # user) -- otherwise this endpoint would let anyone holding the invite link
        # take over an existing account with no password check.
        if current_auth is None or current_auth.user_id != existing_user.id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"An account already exists for '{invitation.email}'. Log in, then accept this invitation again.",
            )
        user = existing_user
        membership = (
            await db.execute(
                select(Membership).where(Membership.organization_id == invitation.organization_id, Membership.user_id == user.id)
            )
        ).scalar_one_or_none()
        if not membership:
            membership = Membership(
                organization_id=invitation.organization_id,
                user_id=user.id,
                role=invitation.role,
                invited_by_user_id=invitation.invited_by_user_id,
                accepted_at=now,
            )
            db.add(membership)
            await db.flush()
    else:
        if not full_name or not password:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="full_name and password are required to accept this invitation and create an account",
            )
        user = User(
            email=invitation.email,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_active=True,
            # The invite link itself was only reachable via the invitee's inbox, so
            # receiving and using it is a reasonable proof of email ownership.
            is_email_verified=True,
        )
        db.add(user)
        await db.flush()
        membership = Membership(
            organization_id=invitation.organization_id,
            user_id=user.id,
            role=invitation.role,
            invited_by_user_id=invitation.invited_by_user_id,
            accepted_at=now,
        )
        db.add(membership)
        await db.flush()

    invitation.accepted_at = now

    await audit_service.record(
        db,
        organization_id=invitation.organization_id,
        actor_user_id=user.id,
        action=AuditAction.INVITATION_ACCEPTED,
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"email": invitation.email, "role": invitation.role},
        ip_address=ip_address,
    )

    await notifications_service.create(
        db, organization_id=invitation.organization_id, user_id=user.id,
        type="member.joined", title=f"Welcome to {_org.name}",
        body=f"You joined {_org.name} as {invitation.role}.",
        resource_type="membership", resource_id=str(membership.id),
    )
    await notifications_service.notify_org_admins(
        db, organization_id=invitation.organization_id,
        type="member.joined", title="New team member",
        body=f"{invitation.email} joined as {invitation.role}.",
        resource_type="membership", resource_id=str(membership.id),
        exclude_user_id=user.id,
    )

    await db.commit()
    await db.refresh(user)
    await db.refresh(membership)

    return await auth_service._issue_token_pair(db, user, membership, ip=ip_address, user_agent=None)


async def list_invitations(
    db: AsyncSession, *, organization_id: uuid.UUID, status_filter: str | None = None
) -> list[Invitation]:
    """Newest first. Filtering by derived `status` happens in Python since it isn't a
    stored column (see Invitation.status)."""
    invitations = (
        await db.execute(
            select(Invitation).where(Invitation.organization_id == organization_id).order_by(Invitation.created_at.desc())
        )
    ).scalars().all()
    if status_filter:
        invitations = [inv for inv in invitations if inv.status == status_filter]
    return list(invitations)


async def revoke_invitation(
    db: AsyncSession, *, organization_id: uuid.UUID, invitation_id: uuid.UUID, actor_user_id: uuid.UUID, ip_address: str | None
) -> Invitation:
    invitation = (
        await db.execute(select(Invitation).where(Invitation.id == invitation_id, Invitation.organization_id == organization_id))
    ).scalar_one_or_none()
    if not invitation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if invitation.accepted_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cannot revoke an already-accepted invitation")
    if invitation.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Invitation is already revoked")

    invitation.revoked_at = datetime.now(timezone.utc)

    await audit_service.record(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction.INVITATION_REVOKED,
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"email": invitation.email},
        ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(invitation)
    return invitation


async def resend_invitation(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    invitation_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    notification_dispatcher: NotificationDispatcher,
    ip_address: str | None,
) -> Invitation:
    """Reissues a token and expiry on the same invitation row (rather than creating a
    duplicate) and re-sends the email through the existing dispatcher. Only valid for
    a still-pending invitation -- an accepted/revoked one should be handled via
    create_invitation (new invite) instead, same as the UI already does."""
    invitation = (
        await db.execute(select(Invitation).where(Invitation.id == invitation_id, Invitation.organization_id == organization_id))
    ).scalar_one_or_none()
    if not invitation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    if invitation.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_STATUS_MESSAGES.get(invitation.status, "This invitation is no longer valid"))

    org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalar_one()

    raw_token, token_hash = generate_secure_token()
    invitation.hashed_token = token_hash
    invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=settings.INVITATION_TOKEN_EXPIRE_DAYS)

    await audit_service.record(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction.INVITATION_RESENT,
        resource_type="invitation",
        resource_id=str(invitation.id),
        metadata={"email": invitation.email, "role": invitation.role},
        ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(invitation)

    accept_link = f"{settings.FRONTEND_URL}/accept-invitation?token={raw_token}"
    await notification_dispatcher.send(
        channel="email",
        config={"to_address": invitation.email},
        subject=f"You've been invited to join {org.name} on RelayHub",
        message=(
            f"You've been invited to join {org.name} on RelayHub as {invitation.role}. "
            f"This invitation expires in {settings.INVITATION_TOKEN_EXPIRE_DAYS} days.\n\n"
            f"{accept_link}"
        ),
    )

    return invitation
