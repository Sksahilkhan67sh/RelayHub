from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.notification_client import NotificationDispatcher
from app.modules.alerts.models import AlertDeliveryStatus, AlertEvent, AlertRule
from app.modules.alerts.schemas import CreateAlertRuleRequest, UpdateAlertRuleRequest


async def create_alert_rule(db: AsyncSession, *, organization_id: uuid.UUID, data: CreateAlertRuleRequest) -> AlertRule:
    rule = AlertRule(
        organization_id=organization_id,
        condition_type=data.condition_type.value,
        severity=data.severity.value,
        channel=data.channel.value,
        channel_config=data.channel_config,
        threshold_config=data.threshold_config,
        throttle_window_minutes=data.throttle_window_minutes,
        is_enabled=data.is_enabled,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def list_alert_rules(db: AsyncSession, *, organization_id: uuid.UUID) -> list[AlertRule]:
    result = await db.execute(
        select(AlertRule).where(AlertRule.organization_id == organization_id).order_by(AlertRule.created_at.desc())
    )
    return list(result.scalars().all())


async def _get_rule_or_404(db: AsyncSession, *, organization_id: uuid.UUID, rule_id: uuid.UUID) -> AlertRule:
    rule = (
        await db.execute(select(AlertRule).where(AlertRule.id == rule_id, AlertRule.organization_id == organization_id))
    ).scalar_one_or_none()
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert rule not found")
    return rule


async def update_alert_rule(
    db: AsyncSession, *, organization_id: uuid.UUID, rule_id: uuid.UUID, data: UpdateAlertRuleRequest
) -> AlertRule:
    rule = await _get_rule_or_404(db, organization_id=organization_id, rule_id=rule_id)
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field in ("severity", "channel") and value is not None:
            value = value.value if hasattr(value, "value") else value
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_alert_rule(db: AsyncSession, *, organization_id: uuid.UUID, rule_id: uuid.UUID) -> None:
    rule = await _get_rule_or_404(db, organization_id=organization_id, rule_id=rule_id)
    await db.delete(rule)
    await db.commit()


async def list_alert_history(
    db: AsyncSession, *, organization_id: uuid.UUID, condition_type: str | None = None, limit: int = 50, offset: int = 0
) -> list[AlertEvent]:
    query = (
        select(AlertEvent)
        .where(AlertEvent.organization_id == organization_id)
        .order_by(AlertEvent.triggered_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if condition_type:
        query = query.where(AlertEvent.condition_type == condition_type)
    result = await db.execute(query)
    return list(result.scalars().all())


def _build_dedup_key(*, organization_id: uuid.UUID, condition_type: str, resource_id: str | None) -> str:
    return f"{organization_id}:{condition_type}:{resource_id or 'global'}"


async def trigger_alert(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    condition_type: str,
    message: str,
    resource_id: str | None = None,
    metadata: dict | None = None,
    notification_dispatcher: NotificationDispatcher,
) -> AlertEvent | None:
    """
    Finds enabled rules for this org+condition, applies dedup/throttling, and sends
    through the configured channel. Returns None (no-op) if no rule is configured for
    this condition -- alerting is opt-in per org, matching "per-org alert preferences".

    If multiple enabled rules exist for the same condition_type (e.g. one Slack rule
    and one email rule), each is evaluated and notified independently, but they share
    ONE dedup_key/history row per rule -- so muting one channel doesn't suppress the
    other.
    """
    rules_result = await db.execute(
        select(AlertRule).where(
            AlertRule.organization_id == organization_id,
            AlertRule.condition_type == condition_type,
            AlertRule.is_enabled.is_(True),
        )
    )
    rules = rules_result.scalars().all()
    if not rules:
        return None

    now = datetime.now(timezone.utc)
    last_event: AlertEvent | None = None

    for rule in rules:
        dedup_key = _build_dedup_key(organization_id=organization_id, condition_type=condition_type, resource_id=resource_id)
        cutoff = now - timedelta(minutes=rule.throttle_window_minutes)

        recent = (
            await db.execute(
                select(AlertEvent).where(
                    AlertEvent.dedup_key == dedup_key,
                    AlertEvent.alert_rule_id == rule.id,
                    AlertEvent.triggered_at >= cutoff,
                )
            )
        ).scalar_one_or_none()

        if recent is not None:
            # Throttled -- record the suppression for visibility in alert history,
            # but do not attempt delivery.
            event = AlertEvent(
                organization_id=organization_id,
                alert_rule_id=rule.id,
                condition_type=condition_type,
                severity=rule.severity,
                message=message,
                metadata_json=metadata or {},
                resource_id=resource_id,
                dedup_key=dedup_key,
                delivery_status=AlertDeliveryStatus.SUPPRESSED.value,
                triggered_at=now,
            )
            db.add(event)
            await db.commit()
            await db.refresh(event)
            last_event = event
            continue

        event = AlertEvent(
            organization_id=organization_id,
            alert_rule_id=rule.id,
            condition_type=condition_type,
            severity=rule.severity,
            message=message,
            metadata_json=metadata or {},
            resource_id=resource_id,
            dedup_key=dedup_key,
            delivery_status=AlertDeliveryStatus.PENDING.value,
            triggered_at=now,
        )
        db.add(event)
        await db.flush()

        try:
            await notification_dispatcher.send(
                channel=rule.channel, config=rule.channel_config, subject=f"RelayHub alert: {condition_type}", message=message
            )
            event.delivery_status = AlertDeliveryStatus.SENT.value
            event.delivered_at = datetime.now(timezone.utc)
        except Exception as e:  # noqa: BLE001 - alert delivery must never crash the caller; record and move on
            event.delivery_status = AlertDeliveryStatus.FAILED.value
            event.delivery_error = str(e)

        await db.commit()
        await db.refresh(event)
        last_event = event

    return last_event


async def send_test_alert(
    db: AsyncSession, *, organization_id: uuid.UUID, rule_id: uuid.UUID, notification_dispatcher: NotificationDispatcher
) -> AlertEvent:
    rule = await _get_rule_or_404(db, organization_id=organization_id, rule_id=rule_id)

    event = AlertEvent(
        organization_id=organization_id,
        alert_rule_id=rule.id,
        condition_type=rule.condition_type,
        severity=rule.severity,
        message=f"This is a test alert for rule '{rule.condition_type}' on channel '{rule.channel}'.",
        metadata_json={"test": True},
        resource_id=None,
        dedup_key=f"test:{rule.id}:{uuid.uuid4()}",  # test alerts always send, never throttled
        delivery_status=AlertDeliveryStatus.PENDING.value,
        triggered_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()

    try:
        await notification_dispatcher.send(
            channel=rule.channel, config=rule.channel_config, subject="RelayHub test alert", message=event.message
        )
        event.delivery_status = AlertDeliveryStatus.SENT.value
        event.delivered_at = datetime.now(timezone.utc)
    except Exception as e:  # noqa: BLE001 - same rationale as trigger_alert above
        event.delivery_status = AlertDeliveryStatus.FAILED.value
        event.delivery_error = str(e)

    await db.commit()
    await db.refresh(event)
    return event
