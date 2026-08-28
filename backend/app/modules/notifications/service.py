from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import Notification


async def create(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> Notification:
    """
    Adds a notification to the session without committing -- same convention as
    audit_service.record. Callers create a notification as part of the same
    transaction as the event that caused it (e.g. accepting an invitation),
    so a notification never exists for an action that itself rolled back.
    """
    notification = Notification(
        organization_id=organization_id,
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    db.add(notification)
    return notification


async def notify_org_admins(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    type: str,
    title: str,
    body: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    exclude_user_id: uuid.UUID | None = None,
) -> None:
    """Fan-out helper: notify every OWNER/ADMIN member of an org (e.g. a new member
    joined, an abuse report was filed against the org). Import is local to avoid a
    circular import between the notifications and auth modules."""
    from app.modules.auth.models import Membership

    admin_user_ids = (
        await db.execute(
            select(Membership.user_id).where(
                Membership.organization_id == organization_id,
                Membership.role.in_(["owner", "admin"]),
            )
        )
    ).scalars().all()

    for admin_user_id in admin_user_ids:
        if exclude_user_id is not None and admin_user_id == exclude_user_id:
            continue
        await create(
            db,
            organization_id=organization_id,
            user_id=admin_user_id,
            type=type,
            title=title,
            body=body,
            resource_type=resource_type,
            resource_id=resource_id,
        )


async def list_notifications(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 30,
    offset: int = 0,
) -> list[Notification]:
    stmt = select(Notification).where(
        Notification.organization_id == organization_id,
        Notification.user_id == user_id,
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def get_unread_count(db: AsyncSession, *, organization_id: uuid.UUID, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.organization_id == organization_id,
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
    )
    return int(result.scalar_one())


async def mark_read(
    db: AsyncSession, *, organization_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification:
    notification = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.organization_id == organization_id,
                Notification.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not notification:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(notification)
    return notification


async def mark_all_read(db: AsyncSession, *, organization_id: uuid.UUID, user_id: uuid.UUID) -> int:
    result = await db.execute(
        update(Notification)
        .where(
            Notification.organization_id == organization_id,
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return result.rowcount or 0
