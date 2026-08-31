from __future__ import annotations

import csv
import io
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


# Hard ceiling on rows returned in a single CSV export. Not user-configurable --
# exists purely to keep one export request from trying to pull an organization's
# entire delivery history into memory at once. Large historical pulls should use
# the paginated /v1/logs search endpoint with queued_after/queued_before instead.
EXPORT_MAX_ROWS = 20000


async def export_delivery_logs_csv(
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
) -> str:
    """
    Full delivery + retry history for every matching job (default: no status
    filter, so queued/processing/success/retrying/failed/dead_letter are all
    included -- not just the terminal failed/dead_letter jobs the DLQ export
    covers).

    One row per delivery ATTEMPT rather than per job, so a job that failed twice
    before eventually succeeding shows up as three rows -- one per attempt, in
    order -- and it's visible exactly which attempt(s) failed, with what error,
    versus which attempt (if any) finally went through. A job with no attempts
    yet (still sitting in `queued`) still gets one row, with attempt-specific
    columns left blank, so nothing waiting in the retry queue is silently
    dropped from the export. Every row also carries the full endpoint record
    (name, URL, environment, health, active/paused state, failure streak) so
    the export is self-contained without cross-referencing the Endpoints page.
    """
    from app.modules.retry.schedule import DEFAULT_MAX_ATTEMPTS

    jobs = await search_delivery_logs(
        db,
        organization_id=organization_id,
        endpoint_id=endpoint_id,
        statuses=statuses,
        event_type=event_type,
        environment=environment,
        request_id=request_id,
        worker_id=worker_id,
        queued_after=queued_after,
        queued_before=queued_before,
        min_latency_ms=min_latency_ms,
        max_latency_ms=max_latency_ms,
        limit=EXPORT_MAX_ROWS,
        offset=0,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            # -- event / job identity --
            "delivery_job_id", "event_id", "event_type", "environment", "request_id",
            # -- endpoint (every endpoint field relevant to delivery) --
            "endpoint_id", "endpoint_name", "endpoint_url", "endpoint_environment",
            "endpoint_is_active", "endpoint_health_status", "endpoint_consecutive_failure_count",
            "endpoint_paused_at", "endpoint_paused_reason",
            # -- job / retry-queue state (overall outcome for this job) --
            "job_status", "job_total_attempts_so_far", "job_max_attempts",
            "job_queued_at", "job_next_attempt_at", "job_completed_at",
            # -- this specific attempt (one row per attempt -- the retry history) --
            "attempt_number", "attempt_outcome", "attempt_queued_at", "attempt_started_at",
            "attempt_completed_at", "attempt_duration_ms", "attempt_http_status",
            "attempt_error_category", "attempt_error_message", "attempt_worker_id",
            "attempt_region", "attempt_destination_ip",
        ]
    )

    for job in jobs:
        ep = job.endpoint
        effective_max_attempts = (
            ep.max_retry_attempts if ep and ep.max_retry_attempts is not None else DEFAULT_MAX_ATTEMPTS
        )
        job_fields = [
            str(job.id), str(job.event_id), job.event.event_type if job.event else "",
            job.event.environment if job.event else "", job.event.request_id if job.event else "",
            str(job.endpoint_id), ep.name if ep else "", ep.url if ep else "",
            ep.environment if ep else "", ep.is_active if ep else "", ep.health_status if ep else "",
            ep.consecutive_failure_count if ep else "",
            ep.paused_at.isoformat() if ep and ep.paused_at else "",
            ep.paused_reason if ep else "",
            job.status, job.attempt_number, effective_max_attempts,
            job.queued_at.isoformat() if job.queued_at else "",
            job.next_attempt_at.isoformat() if job.next_attempt_at else "",
            job.completed_at.isoformat() if job.completed_at else "",
        ]

        if not job.attempts:
            # Nothing has been attempted yet (e.g. still sitting in `queued`) --
            # still emit the job/endpoint context with blank attempt columns.
            writer.writerow(job_fields + ["", "", "", "", "", "", "", "", "", "", "", ""])
            continue

        for attempt in job.attempts:
            outcome = "success" if attempt.error_category == "none" and attempt.http_status and 200 <= attempt.http_status < 300 else "failed"
            writer.writerow(
                job_fields
                + [
                    attempt.attempt_number,
                    outcome,
                    attempt.queued_at.isoformat() if attempt.queued_at else "",
                    attempt.started_at.isoformat() if attempt.started_at else "",
                    attempt.completed_at.isoformat() if attempt.completed_at else "",
                    attempt.duration_ms,
                    attempt.http_status if attempt.http_status is not None else "",
                    attempt.error_category,
                    attempt.error_message or "",
                    attempt.worker_id,
                    attempt.region,
                    attempt.destination_ip or "",
                ]
            )
    return buffer.getvalue()
