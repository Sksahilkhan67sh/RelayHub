from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.percentiles import compute_percentiles
from app.modules.analytics.time_buckets import dialect_name_for, truncate_timestamp
from app.modules.delivery.models import DeliveryAttempt, DeliveryJob, DeliveryJobStatus
from app.modules.endpoints.models import Endpoint
from app.modules.events.models import Event


def _apply_date_range(query, column, start_date: datetime | None, end_date: datetime | None):
    if start_date is not None:
        query = query.where(column >= start_date)
    if end_date is not None:
        query = query.where(column <= end_date)
    return query


async def get_summary(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    environment: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    events_query = select(func.count(Event.id)).where(Event.organization_id == organization_id)
    if environment:
        events_query = events_query.where(Event.environment == environment)
    events_query = _apply_date_range(events_query, Event.created_at, start_date, end_date)
    total_events = (await db.execute(events_query)).scalar_one()

    # A single published event fans out to every endpoint subscribed to its event
    # type, creating one DeliveryJob row per endpoint (see events/service.py). That
    # fan-out is correct and intentional, but counting raw DeliveryJob rows on the
    # dashboard made a 3-endpoint org's "3 events published" look like "9 deliveries,
    # 9 fails/successes" -- confusing when what the person actually published was 3
    # events. This block instead classifies each EVENT once, using the worst-case
    # status across all of that event's fanned-out jobs, so the dashboard's delivery
    # counts line up 1:1 with events published:
    #   any job still in flight (queued/processing/retrying) -> event is "retrying"
    #   else any job dead-lettered                             -> event is "dead_letter"
    #   else any job failed                                     -> event is "failed"
    #   else (every job succeeded)                              -> event is "success"
    in_flight_statuses = (DeliveryJobStatus.QUEUED.value, DeliveryJobStatus.PROCESSING.value, DeliveryJobStatus.RETRYING.value)

    per_event_jobs_query = (
        select(
            DeliveryJob.event_id,
            func.bool_or(DeliveryJob.status.in_(in_flight_statuses)).label("has_pending"),
            func.bool_or(DeliveryJob.status == DeliveryJobStatus.DEAD_LETTER.value).label("has_dead_letter"),
            func.bool_or(DeliveryJob.status == DeliveryJobStatus.FAILED.value).label("has_failed"),
        )
        .select_from(DeliveryJob)
        .where(DeliveryJob.organization_id == organization_id, DeliveryJob.deleted_at.is_(None))
    )
    if environment:
        per_event_jobs_query = per_event_jobs_query.join(Event, Event.id == DeliveryJob.event_id).where(
            Event.environment == environment
        )
    per_event_jobs_query = _apply_date_range(per_event_jobs_query, DeliveryJob.queued_at, start_date, end_date)
    per_event_jobs_query = per_event_jobs_query.group_by(DeliveryJob.event_id).subquery()

    event_status = case(
        (per_event_jobs_query.c.has_pending, "retrying"),
        (per_event_jobs_query.c.has_dead_letter, "dead_letter"),
        (per_event_jobs_query.c.has_failed, "failed"),
        else_="success",
    )

    classification_query = select(
        func.count().label("total"),
        func.sum(case((event_status == "success", 1), else_=0)).label("success"),
        func.sum(case((event_status == "failed", 1), else_=0)).label("failed"),
        func.sum(case((event_status == "retrying", 1), else_=0)).label("retrying"),
        func.sum(case((event_status == "dead_letter", 1), else_=0)).label("dead_letter"),
    ).select_from(per_event_jobs_query)

    total_deliveries, success_count, failed_count, retrying_count, dead_letter_count = (
        await db.execute(classification_query)
    ).one()
    total_deliveries = total_deliveries or 0
    success_count = success_count or 0
    failed_count = failed_count or 0
    retrying_count = retrying_count or 0
    dead_letter_count = dead_letter_count or 0

    latency_query = (
        select(DeliveryAttempt.duration_ms)
        .select_from(DeliveryAttempt)
        .join(DeliveryJob, DeliveryJob.id == DeliveryAttempt.delivery_job_id)
        .where(DeliveryAttempt.organization_id == organization_id)
    )
    if environment:
        latency_query = latency_query.join(Event, Event.id == DeliveryJob.event_id).where(Event.environment == environment)
    latency_query = _apply_date_range(latency_query, DeliveryAttempt.started_at, start_date, end_date)

    durations = [row[0] for row in (await db.execute(latency_query)).all()]
    percentiles = compute_percentiles(durations, [50, 95, 99])

    success_rate = (success_count / total_deliveries) if total_deliveries else None
    failure_rate = ((failed_count + dead_letter_count) / total_deliveries) if total_deliveries else None

    return {
        "total_events": total_events,
        "total_deliveries": total_deliveries,
        "success_count": success_count,
        "failed_count": failed_count,
        "retrying_count": retrying_count,
        "dead_letter_count": dead_letter_count,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "latency_p50_ms": percentiles[50],
        "latency_p95_ms": percentiles[95],
        "latency_p99_ms": percentiles[99],
    }


async def get_deliveries_over_time(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    granularity: str = "hour",
    environment: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    dialect_name = dialect_name_for(db)

    # Same per-event classification as get_summary: a fanned-out event's jobs all
    # queue at effectively the same instant, so bucketing by each event's earliest
    # job (MIN(queued_at)) keeps every job for one event in the same bucket, and we
    # count the event once rather than once per subscribed endpoint.
    in_flight_statuses = (DeliveryJobStatus.QUEUED.value, DeliveryJobStatus.PROCESSING.value, DeliveryJobStatus.RETRYING.value)

    per_event_query = (
        select(
            DeliveryJob.event_id,
            func.min(DeliveryJob.queued_at).label("event_queued_at"),
            func.bool_or(DeliveryJob.status.in_(in_flight_statuses)).label("has_pending"),
            func.bool_or(
                DeliveryJob.status.in_((DeliveryJobStatus.FAILED.value, DeliveryJobStatus.DEAD_LETTER.value))
            ).label("has_failure"),
        )
        .select_from(DeliveryJob)
        .where(DeliveryJob.organization_id == organization_id, DeliveryJob.deleted_at.is_(None))
    )
    if environment:
        per_event_query = per_event_query.join(Event, Event.id == DeliveryJob.event_id).where(
            Event.environment == environment
        )
    per_event_query = _apply_date_range(per_event_query, DeliveryJob.queued_at, start_date, end_date)
    per_event_query = per_event_query.group_by(DeliveryJob.event_id).subquery()

    bucket_expr = truncate_timestamp(per_event_query.c.event_queued_at, granularity=granularity, dialect_name=dialect_name)  # type: ignore[arg-type]

    # Matches get_summary's per-event semantics: an event counts as "success" only
    # once every fanned-out job has succeeded (no pending, no failure); "failed"
    # covers failed/dead-lettered events; still-pending events are counted in the
    # bucket total but not in either bucket, same as the original per-job behavior.
    is_success = per_event_query.c.has_pending.is_(False) & per_event_query.c.has_failure.is_(False)
    is_failed = per_event_query.c.has_failure.is_(True)

    query = (
        select(
            bucket_expr.label("bucket"),
            func.count().label("total"),
            func.sum(case((is_success, 1), else_=0)).label("success"),
            func.sum(case((is_failed, 1), else_=0)).label("failed"),
        )
        .select_from(per_event_query)
        .group_by(bucket_expr)
        .order_by(bucket_expr)
    )

    rows = (await db.execute(query)).all()
    return [
        {"bucket": str(bucket), "total_count": total or 0, "success_count": success or 0, "failed_count": failed or 0}
        for bucket, total, success, failed in rows
    ]


async def get_events_by_type(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    environment: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    query = (
        select(Event.event_type, func.count(Event.id))
        .where(Event.organization_id == organization_id)
        .group_by(Event.event_type)
        .order_by(func.count(Event.id).desc())
    )
    if environment:
        query = query.where(Event.environment == environment)
    query = _apply_date_range(query, Event.created_at, start_date, end_date)

    rows = (await db.execute(query)).all()
    return [{"event_type": event_type, "count": count} for event_type, count in rows]


async def get_top_endpoints(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    limit: int = 10,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    # Job-level counts (delivery_count, success_count) computed WITHOUT joining
    # DeliveryAttempt -- joining it here would multiply each job row once per attempt
    # it has, inflating both COUNT and SUM(case). Latency is aggregated separately.
    counts_query = (
        select(
            Endpoint.id,
            Endpoint.name,
            func.count(DeliveryJob.id),
            func.sum(case((DeliveryJob.status == DeliveryJobStatus.SUCCESS.value, 1), else_=0)),
        )
        .select_from(Endpoint)
        .join(DeliveryJob, DeliveryJob.endpoint_id == Endpoint.id)
        .where(Endpoint.organization_id == organization_id, DeliveryJob.deleted_at.is_(None))
        .group_by(Endpoint.id, Endpoint.name)
        .order_by(func.count(DeliveryJob.id).desc())
        .limit(limit)
    )
    counts_query = _apply_date_range(counts_query, DeliveryJob.queued_at, start_date, end_date)
    count_rows = (await db.execute(counts_query)).all()

    if not count_rows:
        return []

    top_endpoint_ids = [row[0] for row in count_rows]

    latency_query = (
        select(Endpoint.id, func.avg(DeliveryAttempt.duration_ms))
        .select_from(Endpoint)
        .join(DeliveryJob, DeliveryJob.endpoint_id == Endpoint.id)
        .join(DeliveryAttempt, DeliveryAttempt.delivery_job_id == DeliveryJob.id)
        .where(Endpoint.organization_id == organization_id, DeliveryJob.deleted_at.is_(None), Endpoint.id.in_(top_endpoint_ids))
        .group_by(Endpoint.id)
    )
    latency_query = _apply_date_range(latency_query, DeliveryJob.queued_at, start_date, end_date)
    avg_latency_by_endpoint = {row[0]: row[1] for row in (await db.execute(latency_query)).all()}

    results = []
    for endpoint_id, name, delivery_count, success_count in count_rows:
        delivery_count = delivery_count or 0
        success_count = success_count or 0
        avg_latency = avg_latency_by_endpoint.get(endpoint_id)
        results.append(
            {
                "endpoint_id": endpoint_id,
                "name": name,
                "delivery_count": delivery_count,
                "success_count": success_count,
                "success_rate": (success_count / delivery_count) if delivery_count else None,
                "avg_latency_ms": float(avg_latency) if avg_latency is not None else None,
            }
        )
    return results


async def get_endpoint_health(db: AsyncSession, *, organization_id: uuid.UUID):
    query = select(Endpoint).where(Endpoint.organization_id == organization_id, Endpoint.deleted_at.is_(None))
    endpoints = (await db.execute(query)).scalars().all()
    return [
        {
            "endpoint_id": ep.id,
            "name": ep.name,
            "health_status": ep.health_status,
            "consecutive_failure_count": ep.consecutive_failure_count,
            "last_success_at": ep.last_success_at,
            "last_failure_at": ep.last_failure_at,
            "is_active": ep.is_active,
        }
        for ep in endpoints
    ]
