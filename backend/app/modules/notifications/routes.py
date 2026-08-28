import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role
from app.modules.notifications import service
from app.modules.notifications.schemas import NotificationOut, UnreadCountOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_notifications(
        db, organization_id=auth.organization_id, user_id=auth.user_id,
        unread_only=unread_only, limit=limit, offset=offset,
    )


@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(
    auth: AuthContext = Depends(require_role(Role.VIEWER)), db: AsyncSession = Depends(get_db)
):
    count = await service.get_unread_count(db, organization_id=auth.organization_id, user_id=auth.user_id)
    return UnreadCountOut(unread_count=count)


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    return await service.mark_read(
        db, organization_id=auth.organization_id, user_id=auth.user_id, notification_id=notification_id
    )


@router.post("/read-all", response_model=UnreadCountOut)
async def mark_all_read(
    auth: AuthContext = Depends(require_role(Role.VIEWER)), db: AsyncSession = Depends(get_db)
):
    await service.mark_all_read(db, organization_id=auth.organization_id, user_id=auth.user_id)
    return UnreadCountOut(unread_count=0)
