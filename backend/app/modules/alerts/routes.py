import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.notification_client import NotificationDispatcher, get_notification_dispatcher
from app.db.session import get_db
from app.modules.alerts import service
from app.modules.alerts.schemas import (
    AlertEventOut,
    AlertRuleOut,
    CreateAlertRuleRequest,
    TestAlertResponse,
    UpdateAlertRuleRequest,
)
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("/rules", response_model=AlertRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: CreateAlertRuleRequest,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_alert_rule(db, organization_id=auth.organization_id, data=payload)


@router.get("/rules", response_model=list[AlertRuleOut])
async def list_rules(auth: AuthContext = Depends(require_role(Role.VIEWER)), db: AsyncSession = Depends(get_db)):
    return await service.list_alert_rules(db, organization_id=auth.organization_id)


@router.patch("/rules/{rule_id}", response_model=AlertRuleOut)
async def update_rule(
    rule_id: uuid.UUID,
    payload: UpdateAlertRuleRequest,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_alert_rule(db, organization_id=auth.organization_id, rule_id=rule_id, data=payload)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: uuid.UUID, auth: AuthContext = Depends(require_role(Role.ADMIN)), db: AsyncSession = Depends(get_db)
):
    await service.delete_alert_rule(db, organization_id=auth.organization_id, rule_id=rule_id)


@router.post("/rules/{rule_id}/test", response_model=TestAlertResponse)
async def test_rule(
    rule_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
    notification_dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    event = await service.send_test_alert(
        db, organization_id=auth.organization_id, rule_id=rule_id, notification_dispatcher=notification_dispatcher
    )
    return TestAlertResponse(delivery_status=event.delivery_status, delivery_error=event.delivery_error)


@router.get("/history", response_model=list[AlertEventOut])
async def alert_history(
    condition_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_alert_history(
        db, organization_id=auth.organization_id, condition_type=condition_type, limit=limit, offset=offset
    )
