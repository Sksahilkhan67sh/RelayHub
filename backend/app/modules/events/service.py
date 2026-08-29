from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.queue_client import QueueClient
from app.common.realtime_publisher import RealtimePublisher
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus
from app.modules.endpoints.models import Endpoint
from app.modules.events.models import BUILT_IN_EVENT_TYPES, Event, EventType
from app.modules.events.schemas import PublishEventRequest
from app.modules.realtime.events import emit_delivery_update

logger = logging.getLogger(__name__)


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


async def _matching_endpoints(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    event_type: str,
    environment: str,
    endpoint_ids: list[uuid.UUID] | None = None,
) -> list[Endpoint]:
    query = select(Endpoint).where(
        Endpoint.organization_id == organization_id,
        Endpoint.environment == environment,
        Endpoint.is_active.is_(True),
        Endpoint.deleted_at.is_(None),
    )
    if endpoint_ids is not None:
        # Caller explicitly picked endpoints -- deliver to exactly those (that still
        # belong to this org/environment/are active), bypassing the subscribed_event_types
        # filter below. An explicit selection is a stronger signal than a standing subscription.
        query = query.where(Endpoint.id.in_(endpoint_ids))
        result = await db.execute(query)
        return list(result.scalars().all())

    result = await db.execute(query)
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
    realtime_publisher: RealtimePublisher | None = None,
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
        db,
        organization_id=organization_id,
        event_type=data.event,
        environment=data.environment.value,
        endpoint_ids=data.endpoint_ids,
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
    #
    # Reliability fix: the event + DeliveryJob rows above are already durably
    # committed at this point -- that part can't fail silently. But until this fix,
    # a broker/Redis outage during THIS enqueue call would raise past the caller,
    # turning a successfully-persisted publish into a 500 the customer would
    # reasonably read as "the event was never accepted" and might re-publish
    # (masking, not preventing, the real gap). The job is not lost -- it's sitting
    # in the DB with status=queued -- but nothing would dispatch it until an
    # operator noticed and manually intervened. Catch broker failures here, log
    # them, and let `reconcile_stuck_jobs` (runs every 60s) pick up the row from
    # its durable `queued` state and retry the dispatch instead.
    for job in jobs:
        try:
            await queue_client.enqueue(job.id)
        except Exception:  # noqa: BLE001 - broker outage must not fail an already-durable publish
            logger.exception(
                "queue dispatch failed for delivery_job=%s (event=%s) -- job remains queued in the "
                "database and will be picked up by reconciliation",
                job.id, event.id,
            )

    # Realtime "queued" notification -- strictly after the commit above.
    # Failure-isolated inside emit_delivery_update: a publisher problem here can
    # never turn an already-durably-committed publish into a failed request.
    if realtime_publisher is not None:
        max_attempts_by_endpoint = {ep.id: ep.max_retry_attempts for ep in matching}
        for job in jobs:
            await emit_delivery_update(
                realtime_publisher,
                organization_id=organization_id,
                delivery_job_id=job.id,
                event_id=event.id,
                endpoint_id=job.endpoint_id,
                status=DeliveryJobStatus.QUEUED.value,
                attempt_number=job.attempt_number,
                queued_at=job.queued_at,
                max_attempts=max_attempts_by_endpoint.get(job.endpoint_id),
            )

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
