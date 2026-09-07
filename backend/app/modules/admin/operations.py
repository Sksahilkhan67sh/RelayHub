from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import WorkerHeartbeat
from app.modules.audit import service as audit_service
from app.modules.audit.models import AuditAction
from app.modules.auth.models import Organization
from app.modules.billing.models import Plan, Subscription, SubscriptionStatus
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus

logger = logging.getLogger(__name__)


async def get_queue_depth(db: AsyncSession) -> dict:
    async def _count(status_value: str) -> int:
        return (
            await db.execute(select(func.count(DeliveryJob.id)).where(DeliveryJob.status == status_value, DeliveryJob.deleted_at.is_(None)))
        ).scalar_one()

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    success_last_hour = (
        await db.execute(
            select(func.count(DeliveryJob.id)).where(
                DeliveryJob.status == DeliveryJobStatus.SUCCESS.value, DeliveryJob.completed_at >= one_hour_ago
            )
        )
    ).scalar_one()
    failed_last_hour = (
        await db.execute(
            select(func.count(DeliveryJob.id)).where(
                DeliveryJob.status.in_([DeliveryJobStatus.FAILED.value, DeliveryJobStatus.DEAD_LETTER.value]),
                DeliveryJob.completed_at >= one_hour_ago,
            )
        )
    ).scalar_one()

    return {
        "queued": await _count(DeliveryJobStatus.QUEUED.value),
        "processing": await _count(DeliveryJobStatus.PROCESSING.value),
        "retrying": await _count(DeliveryJobStatus.RETRYING.value),
        "dead_letter": await _count(DeliveryJobStatus.DEAD_LETTER.value),
        "success_last_hour": success_last_hour,
        "failed_last_hour": failed_last_hour,
    }


# How long a job may sit in `processing` before this read-only metric counts it as
# "stuck" for dashboard purposes. Intentionally the same threshold
# `reconcile_stuck_jobs` uses as its own time-heuristic fallback (see
# retry/reconciliation.py) so this number means the same thing an operator would
# expect: "how many jobs would reconciliation's fallback path act on right now".
# Duplicated rather than imported for the same reason this file's own
# WORKER_HEARTBEAT_STALE_AFTER is duplicated in reconciliation.py -- the two
# modules are allowed to tune their thresholds independently over time.
METRICS_STUCK_PROCESSING_AFTER = timedelta(minutes=10)


async def get_delivery_metrics(db: AsyncSession, *, window: timedelta = timedelta(hours=1)) -> dict:
    """
    Phase 2 section 16 ("Observability") asks for delivery latency, retry rate, DLQ
    rate, and stuck-job visibility beyond what `get_queue_depth` already covers
    (queue depth by status, success/failure counts). This is the rest of that list,
    computed directly from existing tables -- no new dependency, consistent with
    the "avoid unnecessary dependencies, use the existing monitoring architecture"
    instruction, since there was no metrics-export pipeline to plug into.
    """
    now = datetime.now(timezone.utc)
    window_start = now - window

    from app.modules.delivery.models import DeliveryAttempt  # local import: avoids a module-level cycle with delivery

    durations = (
        await db.execute(
            select(DeliveryAttempt.duration_ms).where(
                DeliveryAttempt.completed_at >= window_start, DeliveryAttempt.error_category == "none"
            )
        )
    ).scalars().all()
    sorted_durations = sorted(durations)
    avg_latency_ms = (sum(sorted_durations) / len(sorted_durations)) if sorted_durations else None
    p95_latency_ms = (
        sorted_durations[min(int(len(sorted_durations) * 0.95), len(sorted_durations) - 1)]
        if sorted_durations
        else None
    )

    completed_in_window = (
        await db.execute(
            select(DeliveryJob.status, DeliveryJob.attempt_number).where(
                DeliveryJob.status.in_(
                    [DeliveryJobStatus.SUCCESS.value, DeliveryJobStatus.FAILED.value, DeliveryJobStatus.DEAD_LETTER.value]
                ),
                DeliveryJob.completed_at >= window_start,
            )
        )
    ).all()
    total_completed = len(completed_in_window)
    retried_count = sum(1 for row in completed_in_window if row.attempt_number > 1)
    dead_lettered_count = sum(1 for row in completed_in_window if row.status == DeliveryJobStatus.DEAD_LETTER.value)
    retry_rate = (retried_count / total_completed) if total_completed else None
    dlq_rate = (dead_lettered_count / total_completed) if total_completed else None

    stuck_cutoff = now - METRICS_STUCK_PROCESSING_AFTER
    stuck_jobs_count = (
        await db.execute(
            select(func.count(DeliveryJob.id)).where(
                DeliveryJob.status == DeliveryJobStatus.PROCESSING.value,
                DeliveryJob.updated_at < stuck_cutoff,
                DeliveryJob.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    return {
        "window_seconds": int(window.total_seconds()),
        "avg_delivery_latency_ms": avg_latency_ms,
        "p95_delivery_latency_ms": p95_latency_ms,
        "retry_rate": retry_rate,
        "dlq_rate": dlq_rate,
        "stuck_jobs_count": stuck_jobs_count,
        "sample_size": total_completed,
    }


# A worker whose heartbeat is older than this is considered unhealthy/gone -- a few
# multiples of the heartbeat write interval (HEARTBEAT_INTERVAL_SECONDS in
# app/workers/celery_app.py) so a single missed tick under load doesn't flip a
# healthy worker to "unhealthy".
WORKER_HEARTBEAT_STALE_AFTER = timedelta(seconds=90)


async def upsert_worker_heartbeat(
    db: AsyncSession, *, worker_id: str, hostname: str, pid: int, now: datetime | None = None
) -> None:
    """
    Called by the heartbeat loop each worker process runs in the background (see
    app/workers/celery_app.py's `worker_process_init` handler). `worker_id`
    (hostname-pid) is the natural key: a worker process that dies and restarts
    under the same identity just overwrites its own row rather than accumulating
    stale entries, and a process that's actually gone simply stops updating its row
    -- which is exactly the signal `get_worker_health` needs.
    """
    now = now or datetime.now(timezone.utc)
    existing = (
        await db.execute(select(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == worker_id))
    ).scalar_one_or_none()
    if existing:
        existing.last_heartbeat_at = now
    else:
        db.add(
            WorkerHeartbeat(worker_id=worker_id, hostname=hostname, pid=pid, started_at=now, last_heartbeat_at=now)
        )
    await db.commit()


async def get_worker_health(db: AsyncSession, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    stale_cutoff = now - WORKER_HEARTBEAT_STALE_AFTER

    def _is_healthy(last_heartbeat_at: datetime) -> bool:
        # Postgres (production) always round-trips tz-aware DateTime(timezone=True)
        # values; SQLite (the test suite's DB) does not preserve tzinfo on read-back.
        # Normalize defensively so this comparison is correct in both.
        if last_heartbeat_at.tzinfo is None:
            last_heartbeat_at = last_heartbeat_at.replace(tzinfo=timezone.utc)
        return last_heartbeat_at >= stale_cutoff

    all_workers = (await db.execute(select(WorkerHeartbeat))).scalars().all()
    healthy = [w for w in all_workers if _is_healthy(w.last_heartbeat_at)]
    unhealthy = [w for w in all_workers if not _is_healthy(w.last_heartbeat_at)]

    return {
        "healthy_count": len(healthy),
        "unhealthy_count": len(unhealthy),
        "workers": [
            {
                "worker_id": w.worker_id,
                "hostname": w.hostname,
                "pid": w.pid,
                "last_heartbeat_at": w.last_heartbeat_at,
                "healthy": _is_healthy(w.last_heartbeat_at),
            }
            for w in all_workers
        ],
    }


async def get_system_health(db: AsyncSession) -> dict:
    """
    Real checks, not decorative: DB connectivity is verified with an actual query,
    queue depth is the same live aggregation used by the queue-inspection endpoint,
    and worker health is now backed by the real `worker_heartbeats` table (Phase 2)
    instead of the "not tracked yet" gap this endpoint used to honestly report.
    """
    try:
        await db.execute(select(func.count(Organization.id)))
        database_ok = True
    except Exception:  # noqa: BLE001 - health check must never raise, it must report
        database_ok = False

    queue_depth = await get_queue_depth(db)
    worker_health = await get_worker_health(db)
    return {
        "database_ok": database_ok,
        "queue_depth": queue_depth,
        "worker_health": worker_health,
        "checked_at": datetime.now(timezone.utc),
    }


async def get_billing_overview(db: AsyncSession) -> dict:
    total_organizations = (await db.execute(select(func.count(Organization.id)))).scalar_one()

    tier_rows = (
        await db.execute(
            select(Plan.tier, func.count(Subscription.id))
            .select_from(Subscription)
            .join(Plan, Plan.id == Subscription.plan_id)
            .group_by(Plan.tier)
        )
    ).all()
    organizations_by_tier: dict[str, int] = dict(tier_rows)  # type: ignore[arg-type]  # Row[tuple[str,int]] unpacks fine at runtime

    mrr_row = (
        await db.execute(
            select(func.sum(Plan.price_cents))
            .select_from(Subscription)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.status.in_([SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value]))
        )
    ).scalar_one()
    mrr_cents = mrr_row or 0

    start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    canceled_this_month = (
        await db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.CANCELED.value, Subscription.canceled_at >= start_of_month
            )
        )
    ).scalar_one()

    past_due_count = (
        await db.execute(select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.PAST_DUE.value))
    ).scalar_one()

    return {
        "total_organizations": total_organizations, "organizations_by_tier": organizations_by_tier,
        "mrr_cents": mrr_cents, "canceled_this_month": canceled_this_month, "past_due_count": past_due_count,
    }


async def force_retry_delivery_job(
    db: AsyncSession, *, job_id: uuid.UUID, actor_user_id: uuid.UUID, ip_address: str | None, queue_client
) -> DeliveryJob:
    """
    Unlike the customer-facing DLQ retry (Phase 3g), this works on a job in ANY
    status, not just dead_letter -- an admin might need to unstick a job wedged in
    'processing' after a worker crash, which the customer-facing endpoint can't do.
    """
    # tenant-scope: safe - platform admin only (force_requeue), route requires require_platform_admin
    job = (await db.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Delivery job not found")

    job.status = DeliveryJobStatus.QUEUED.value
    job.attempt_number = 0
    job.next_attempt_at = None
    job.completed_at = None
    job.queued_at = datetime.now(timezone.utc)

    await audit_service.record(
        db, organization_id=job.organization_id, actor_user_id=actor_user_id,
        action=AuditAction.ADMIN_DELIVERY_JOB_FORCE_RETRIED, resource_type="delivery_job", resource_id=str(job.id),
        metadata={}, ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(job)

    # Same broker-outage tolerance as the customer-facing DLQ retry and
    # publish_event: the status flip to `queued` is already durably committed, so a
    # dispatch failure here must not fail this admin action or leave the job
    # silently stuck -- reconcile_stuck_jobs' stale-`queued` pass is the backstop.
    try:
        await queue_client.enqueue(job.id)
    except Exception:  # noqa: BLE001 - broker outage must not fail an already-committed force-retry
        logger.exception(
            "queue dispatch failed for admin force-retry of delivery_job=%s -- job remains queued in "
            "the database and will be picked up by reconciliation",
            job.id,
        )
    return job


async def force_cancel_delivery_job(
    db: AsyncSession, *, job_id: uuid.UUID, actor_user_id: uuid.UUID, ip_address: str | None
) -> DeliveryJob:
    # tenant-scope: safe - platform admin only (force_cancel), route requires require_platform_admin
    job = (await db.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Delivery job not found")

    job.status = DeliveryJobStatus.FAILED.value
    job.completed_at = datetime.now(timezone.utc)
    job.next_attempt_at = None

    await audit_service.record(
        db, organization_id=job.organization_id, actor_user_id=actor_user_id,
        action=AuditAction.ADMIN_DELIVERY_JOB_FORCE_CANCELED, resource_type="delivery_job", resource_id=str(job.id),
        metadata={}, ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(job)
    return job


async def admin_search_delivery_jobs(
    db: AsyncSession, *, organization_id: uuid.UUID | None = None, status_filter: str | None = None, limit: int = 50, offset: int = 0
) -> list[DeliveryJob]:
    """
    Deliberately NOT scoped to a single organization by default -- this is the
    "global logs" admin feature and is only reachable behind require_platform_admin.
    Every other logs/search function in this codebase (Phase 3h) DOES scope to one
    org; this function is the one intentional, clearly-marked exception.
    """
    # tenant-scope: safe - platform admin only; org filter applied conditionally below when provided
    query = select(DeliveryJob).where(DeliveryJob.deleted_at.is_(None)).order_by(DeliveryJob.created_at.desc()).limit(limit).offset(offset)
    if organization_id is not None:
        query = query.where(DeliveryJob.organization_id == organization_id)
    if status_filter is not None:
        query = query.where(DeliveryJob.status == status_filter)
    return list((await db.execute(query)).scalars().all())
