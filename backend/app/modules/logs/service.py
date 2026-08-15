from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.delivery.models import DeliveryAttempt, DeliveryJob, DeliveryJobStatus
from app.modules.events.models import Event

# "pending" isn't a real DeliveryJobStatus value -- it's a UX-friendly umbrella the
# spec's status filter list expects, covering jobs that haven't reached a terminal
# state yet.
STATUS_ALIASES: dict[str, list[str]] = {
    "pending": [DeliveryJobStatus.QUEUED.value, DeliveryJobStatus.PROCESSING.value],
}


def _expand_statuses(statuses: list[str]) -> list[str]:
    expanded: list[str] = []
    for s in statuses:
        expanded.extend(STATUS_ALIASES.get(s, [s]))
    return expanded


async def search_delivery_logs(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    endpoint_id: uuid.UUID | None = None,
    statuses: list[str] | None = None,
    event_type: str | None = None,
    environment: str | None = None,
    request_id: str | None = None,
    worker_id: str | None = None,
    queued_after: datetime | None = None,
    queued_before: datetime | None = None,
    min_latency_ms: int | None = None,
    max_latency_ms: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[DeliveryJob]:
    query = (
        select(DeliveryJob)
        .join(Event, DeliveryJob.event_id == Event.id)
        .options(selectinload(DeliveryJob.attempts), selectinload(DeliveryJob.event), selectinload(DeliveryJob.endpoint))
        .where(DeliveryJob.organization_id == organization_id, DeliveryJob.deleted_at.is_(None))
    )

    if endpoint_id is not None:
        query = query.where(DeliveryJob.endpoint_id == endpoint_id)

    if statuses:
        query = query.where(DeliveryJob.status.in_(_expand_statuses(statuses)))

    if event_type is not None:
        query = query.where(Event.event_type == event_type)

    if environment is not None:
        query = query.where(Event.environment == environment)

    if request_id is not None:
        query = query.where(Event.request_id == request_id)

    if queued_after is not None:
        query = query.where(DeliveryJob.queued_at >= queued_after)

    if queued_before is not None:
        query = query.where(DeliveryJob.queued_at <= queued_before)

    # worker_id and latency are attempt-level fields (one-to-many per job) -- use an
    # EXISTS subquery rather than a direct join so a job with multiple attempts isn't
    # returned as duplicate rows.
    if worker_id is not None:
        query = query.where(
            DeliveryJob.id.in_(select(DeliveryAttempt.delivery_job_id).where(DeliveryAttempt.worker_id == worker_id))
        )

    if min_latency_ms is not None or max_latency_ms is not None:
        latency_subquery = select(DeliveryAttempt.delivery_job_id)
        if min_latency_ms is not None:
            latency_subquery = latency_subquery.where(DeliveryAttempt.duration_ms >= min_latency_ms)
        if max_latency_ms is not None:
            latency_subquery = latency_subquery.where(DeliveryAttempt.duration_ms <= max_latency_ms)
        query = query.where(DeliveryJob.id.in_(latency_subquery))

    query = query.order_by(DeliveryJob.queued_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return list(result.scalars().unique().all())
