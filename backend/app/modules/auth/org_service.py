from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import service as audit_service
from app.modules.audit.models import AuditAction
from app.modules.auth.models import Membership, Organization, Role, User


async def list_members(db: AsyncSession, *, organization_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == organization_id)
        .order_by(Membership.created_at.asc())
    )
    rows = result.all()
    return [
        {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": membership.role,
            "invited_by_user_id": membership.invited_by_user_id,
            "accepted_at": membership.accepted_at,
            "joined_at": membership.created_at,
        }
        for membership, user in rows
    ]


async def invite_member(
    db: AsyncSession, *, organization_id: uuid.UUID, email: str, role: Role, actor_user_id: uuid.UUID,
    actor_role: Role, ip_address: str | None
) -> dict:
    """
    Directly adds an existing RelayHub user to the organization, with membership
    active immediately (no separate acceptance step) -- for the invitee-has-no-account
    case, see invitation_service.create_invitation instead, which handles the
    email-token / accept-registration flow.
    """
    if role == Role.OWNER and actor_role != Role.OWNER:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only an existing owner can grant the owner role.",
        )

    invitee = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not invitee:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No RelayHub account exists for '{email}' yet. Ask them to register first, then invite them again.",
        )

    existing = (
        await db.execute(
            select(Membership).where(Membership.organization_id == organization_id, Membership.user_id == invitee.id)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"'{email}' is already a member of this organization")

    membership = Membership(
        organization_id=organization_id,
        user_id=invitee.id,
        role=role.value,
        invited_by_user_id=actor_user_id,
        accepted_at=datetime.now(timezone.utc),
    )
    db.add(membership)

    await audit_service.record(
        db, organization_id=organization_id, actor_user_id=actor_user_id, action=AuditAction.USER_INVITED,
        resource_type="membership", resource_id=str(invitee.id), metadata={"email": email, "role": role.value}, ip_address=ip_address,
    )
    await db.commit()

    return {
        "user_id": invitee.id, "email": invitee.email, "full_name": invitee.full_name, "role": membership.role,
        "invited_by_user_id": membership.invited_by_user_id, "accepted_at": membership.accepted_at, "joined_at": membership.created_at,
    }


async def _count_owners(db: AsyncSession, *, organization_id: uuid.UUID) -> int:
    from sqlalchemy import func

    return (
        await db.execute(
            select(func.count(Membership.id)).where(
                Membership.organization_id == organization_id, Membership.role == Role.OWNER.value
            )
        )
    ).scalar_one()


async def update_member_role(
    db: AsyncSession, *, organization_id: uuid.UUID, target_user_id: uuid.UUID, new_role: Role, actor_user_id: uuid.UUID,
    actor_role: Role,
) -> None:
    membership = (
        await db.execute(
            select(Membership).where(Membership.organization_id == organization_id, Membership.user_id == target_user_id)
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")

    # Changing a role to or from OWNER is itself a change in who has ultimate
    # control of the organization, so -- unlike ordinary admin<->member<->viewer
    # changes -- it requires the actor to already be an owner. Without this, an
    # admin could promote themselves (or an ally) to owner, or demote an existing
    # owner, with no owner ever approving it.
    if (new_role == Role.OWNER or membership.role == Role.OWNER.value) and actor_role != Role.OWNER:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only an existing owner can grant or remove the owner role.",
        )

    if membership.role == Role.OWNER.value and new_role != Role.OWNER and await _count_owners(db, organization_id=organization_id) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cannot demote the last owner. Promote another member to owner first.")

    membership.role = new_role.value
    await db.commit()


async def remove_member(
    db: AsyncSession, *, organization_id: uuid.UUID, target_user_id: uuid.UUID, actor_role: Role,
) -> None:
    membership = (
        await db.execute(
            select(Membership).where(Membership.organization_id == organization_id, Membership.user_id == target_user_id)
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")

    if membership.role == Role.OWNER.value:
        # Same rationale as update_member_role: removing an owner is a change in
        # ultimate control and requires another owner to approve it, not just an admin.
        if actor_role != Role.OWNER:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only an existing owner can remove an owner.")
        if await _count_owners(db, organization_id=organization_id) <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Cannot remove the last owner.")

    await db.delete(membership)
    await db.commit()


async def update_organization(db: AsyncSession, *, organization_id: uuid.UUID, name: str) -> Organization:
    org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalar_one()
    org.name = name
    await db.commit()
    await db.refresh(org)
    return org
