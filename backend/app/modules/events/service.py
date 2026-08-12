from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.queue_client import QueueClient
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus
from app.modules.endpoints.models import Endpoint
from app.modules.events.models import BUILT_IN_EVENT_TYPES, Event, EventType
from app.modules.events.schemas import PublishEventRequest


async def _ensure_event_type_registered(db: AsyncSession, *, organization_id: uuid.UUID, event_type: str) -> None:
    existing = (
        await db.execute(
            select(EventType).where(EventType.organization_id == organization_id, EventType.name == event_type)
        )
    ).scalar_one_or_none()
    if existing:
        return
    db.add(
        EventType(
            organization_id=organization_id,
            name=event_type,
            is_custom=event_type not in BUILT_IN_EVENT_TYPES,
        )
    )
    await db.flush()


async def _matching_endpoints(db: AsyncSession, *, organization_id: uuid.UUID, event_type: str, environment: str) -> list[Endpoint]:
    result = await db.execute(
        select(Endpoint).where(
            Endpoint.organization_id == organization_id,
            Endpoint.environment == environment,
            Endpoint.is_active.is_(True),
            Endpoint.deleted_at.is_(None),
        )
    )
    endpoints = result.scalars().all()
    # Empty subscribed_event_types means "subscribe to everything" -- a common and
    # expected default for a customer's first endpoint, matching Stripe/GitHub-style
    # webhook UX where an unfiltered endpoint receives all event types.
    return [ep for ep in endpoints if not ep.subscribed_event_types or event_type in ep.subscribed_event_types]


async def publish_event(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    api_key_id: uuid.UUID,
    data: PublishEventRequest,
    request_id: str,
    queue_client: QueueClient,
) -> Event:
    # Idempotency: if the client already published this exact idempotency_key for
    # this org, return the original event unchanged rather than creating a duplicate
    # or re-queueing deliveries a second time.
    if data.idempotency_key:
        existing = (
            await db.execute(
                select(Event)
                .options(selectinload(Event.delivery_jobs))
                .where(Event.organization_id == organization_id, Event.idempotency_key == data.idempotency_key)
            )
        ).scalar_one_or_none()
        if existing:
            return existing

    await _ensure_event_type_registered(db, organization_id=organization_id, event_type=data.event)

    event = Event(
        organization_id=organization_id,
        event_type=data.event,
        environment=data.environment.value,
        payload=data.payload,
        idempotency_key=data.idempotency_key,
        request_id=request_id,
        api_key_id=api_key_id,
    )
    db.add(event)

    try:
        await db.flush()
    except IntegrityError as e:
        # Race condition: two concurrent requests with the same idempotency_key both
        # passed the SELECT check above before either committed. Roll back and return
        # whichever one actually won.
        await db.rollback()
        existing = (
            await db.execute(
                select(Event)
                .options(selectinload(Event.delivery_jobs))
                .where(Event.organization_id == organization_id, Event.idempotency_key == data.idempotency_key)
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Duplicate idempotency key") from e

    matching = await _matching_endpoints(
        db, organization_id=organization_id, event_type=data.event, environment=data.environment.value
    )

    now = datetime.now(timezone.utc)
    jobs: list[DeliveryJob] = []
    for endpoint in matching:
        job = DeliveryJob(
            organization_id=organization_id,
            event_id=event.id,
            endpoint_id=endpoint.id,
            status=DeliveryJobStatus.QUEUED.value,
            queued_at=now,
        )
        db.add(job)
        jobs.append(job)

    await db.flush()
    await db.commit()
    await db.refresh(event, attribute_names=["delivery_jobs"])

    # Notify the queue AFTER commit -- never enqueue a job whose row might not
    # actually exist if the transaction were to fail.
    for job in jobs:
        await queue_client.enqueue(job.id)

    if jobs:
        await _maybe_trigger_queue_full_alert(db, organization_id=organization_id)

    return event


# A customer's own backlog (jobs stuck queued/retrying, usually because their
# endpoint can't keep up) crossing this many jobs fires queue_full. This is
# interpreted as a per-org signal -- "your integration isn't keeping pace" -- rather
# than a platform-wide infrastructure metric, since AlertRule is always org-scoped;
# true platform queue-depth belongs to the admin panel's system-health endpoint
# (Phase 3m), which already surfaces it to platform admins.
QUEUE_FULL_THRESHOLD = 500


async def _maybe_trigger_queue_full_alert(db: AsyncSession, *, organization_id: uuid.UUID) -> None:
    from app.common.notification_client import get_notification_dispatcher
    from app.modules.alerts import service as alerts_service
    from app.modules.alerts.models import AlertConditionType

    backlog_count = (
        await db.execute(
            select(func.count(DeliveryJob.id)).where(
                DeliveryJob.organization_id == organization_id,
                DeliveryJob.status.in_([DeliveryJobStatus.QUEUED.value, DeliveryJobStatus.RETRYING.value]),
                DeliveryJob.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    if backlog_count < QUEUE_FULL_THRESHOLD:
        return

    await alerts_service.trigger_alert(
        db,
        organization_id=organization_id,
        condition_type=AlertConditionType.QUEUE_FULL.value,
        message=f"Your organization has {backlog_count} delivery jobs queued or retrying, which exceeds the "
        f"{QUEUE_FULL_THRESHOLD}-job alert threshold. This usually means one or more endpoints can't keep up "
        f"with delivery volume.",
        resource_id=None,
        metadata={"backlog_count": backlog_count},
        notification_dispatcher=get_notification_dispatcher(),
    )


async def get_event(db: AsyncSession, *, organization_id: uuid.UUID, event_id: uuid.UUID) -> Event:
    event = (
        await db.execute(
            select(Event)
            .options(selectinload(Event.delivery_jobs))
            .where(Event.id == event_id, Event.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


async def list_events(db: AsyncSession, *, organization_id: uuid.UUID, limit: int = 50) -> list[Event]:
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.delivery_jobs))
        .where(Event.organization_id == organization_id)
        .order_by(Event.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
