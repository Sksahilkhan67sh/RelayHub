from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import (
    AbuseReport,
    AbuseReportStatus,
    FeatureFlag,
    FeatureFlagOverride,
    WorkerHeartbeat,
)
from app.modules.audit import service as audit_service
from app.modules.audit.models import AuditAction
from app.modules.auth.models import Membership, Organization, Role, User
from app.modules.billing.models import Plan, Subscription, SubscriptionStatus
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus
from app.modules.endpoints.models import Endpoint

logger = logging.getLogger(__name__)


async def list_organizations(db: AsyncSession, *, limit: int = 50, offset: int = 0) -> list[dict]:
    orgs = (
        await db.execute(select(Organization).order_by(Organization.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()

    results = []
    for org in orgs:
        member_count = (
            await db.execute(select(func.count(Membership.id)).where(Membership.organization_id == org.id))
        ).scalar_one()
        endpoint_count = (
            await db.execute(
                select(func.count(Endpoint.id)).where(Endpoint.organization_id == org.id, Endpoint.deleted_at.is_(None))
            )
        ).scalar_one()
        subscription = (
            await db.execute(select(Subscription).where(Subscription.organization_id == org.id))
        ).scalar_one_or_none()
        plan_tier = None
        if subscription:
            plan = (await db.execute(select(Plan).where(Plan.id == subscription.plan_id))).scalar_one_or_none()
            plan_tier = plan.tier if plan else None

        results.append(
            {
                "id": org.id, "name": org.name, "slug": org.slug, "is_suspended": org.is_suspended,
                "suspension_reason": org.suspension_reason, "plan_tier": plan_tier,
                "subscription_status": subscription.status if subscription else None,
                "member_count": member_count, "endpoint_count": endpoint_count, "created_at": org.created_at,
            }
        )
    return results


async def _get_org_or_404(db: AsyncSession, organization_id: uuid.UUID) -> Organization:
    org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalar_one_or_none()
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


async def suspend_organization(
    db: AsyncSession, *, organization_id: uuid.UUID, reason: str, actor_user_id: uuid.UUID, ip_address: str | None
) -> Organization:
    org = await _get_org_or_404(db, organization_id)
    org.is_suspended = True
    org.suspension_reason = reason

    await audit_service.record(
        db, organization_id=organization_id, actor_user_id=actor_user_id, action=AuditAction.ADMIN_ORG_SUSPENDED,
        resource_type="organization", resource_id=str(organization_id), metadata={"reason": reason}, ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(org)
    return org


async def unsuspend_organization(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_user_id: uuid.UUID, ip_address: str | None
) -> Organization:
    org = await _get_org_or_404(db, organization_id)
    org.is_suspended = False
    org.suspension_reason = None

    await audit_service.record(
        db, organization_id=organization_id, actor_user_id=actor_user_id, action=AuditAction.ADMIN_ORG_UNSUSPENDED,
        resource_type="organization", resource_id=str(organization_id), metadata={}, ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(org)
    return org


async def impersonate_organization_owner(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_user_id: uuid.UUID, ip_address: str | None
) -> tuple[str, str, int]:
    """
    Issues a short-lived (5 min, deliberately much shorter than a normal 15-min
    session) access token scoped to the org's owner, so a platform admin can debug a
    customer's exact view of the product. The audit log entry is the accountability
    mechanism -- this is intentionally logged loudly, not a quiet backdoor.
    """
    await _get_org_or_404(db, organization_id)  # raises 404 if the org doesn't exist

    owner_membership = (
        await db.execute(
            select(Membership).where(Membership.organization_id == organization_id, Membership.role == Role.OWNER.value)
        )
    ).scalar_one_or_none()
    if not owner_membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Organization has no owner to impersonate")

    owner = (await db.execute(select(User).where(User.id == owner_membership.user_id))).scalar_one()

    await audit_service.record(
        db, organization_id=organization_id, actor_user_id=actor_user_id, action=AuditAction.ADMIN_IMPERSONATION_STARTED,
        resource_type="organization", resource_id=str(organization_id),
        metadata={"impersonated_user_id": str(owner.id), "impersonated_email": owner.email}, ip_address=ip_address,
    )
    await db.commit()

    import jwt as pyjwt

    from app.core.config import settings

    now = datetime.now(timezone.utc)
    expires_in = 300
    payload = {
        "sub": str(owner.id), "org_id": str(organization_id), "role": owner_membership.role, "type": "access",
        "iat": now, "exp": now + timedelta(seconds=expires_in), "jti": str(uuid.uuid4()), "impersonated_by": str(actor_user_id),
    }
    token = pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, owner.email, expires_in


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
# Duplicated rather than imported for the same reason admin/service.py's own
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


async def create_feature_flag(db: AsyncSession, *, key: str, description: str, is_enabled_globally: bool) -> FeatureFlag:
    existing = (await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Feature flag '{key}' already exists")
    flag = FeatureFlag(key=key, description=description, is_enabled_globally=is_enabled_globally)
    db.add(flag)
    await db.commit()
    await db.refresh(flag)
    return flag


async def list_feature_flags(db: AsyncSession) -> list[FeatureFlag]:
    return list((await db.execute(select(FeatureFlag).order_by(FeatureFlag.key))).scalars().all())


async def _get_flag_or_404(db: AsyncSession, key: str) -> FeatureFlag:
    flag = (await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))).scalar_one_or_none()
    if not flag:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Feature flag not found")
    return flag


async def update_feature_flag(
    db: AsyncSession, *, key: str, description: str | None, is_enabled_globally: bool | None,
    actor_user_id: uuid.UUID, ip_address: str | None,
) -> FeatureFlag:
    flag = await _get_flag_or_404(db, key)
    if description is not None:
        flag.description = description
    if is_enabled_globally is not None:
        flag.is_enabled_globally = is_enabled_globally

    await audit_service.record(
        db, organization_id=None, actor_user_id=actor_user_id, action=AuditAction.ADMIN_FEATURE_FLAG_UPDATED,
        resource_type="feature_flag", resource_id=key, metadata={"is_enabled_globally": is_enabled_globally}, ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(flag)
    return flag


async def set_feature_flag_override(db: AsyncSession, *, key: str, organization_id: uuid.UUID, is_enabled: bool) -> None:
    flag = await _get_flag_or_404(db, key)
    existing = (
        await db.execute(
            select(FeatureFlagOverride).where(
                FeatureFlagOverride.flag_id == flag.id, FeatureFlagOverride.organization_id == organization_id
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.is_enabled = is_enabled
    else:
        db.add(FeatureFlagOverride(flag_id=flag.id, organization_id=organization_id, is_enabled=is_enabled))
    await db.commit()


async def list_feature_flag_overrides(db: AsyncSession, *, key: str) -> list[tuple[FeatureFlagOverride, str]]:
    """Returns (override, organization_name) pairs, newest first."""
    flag = await _get_flag_or_404(db, key)
    rows = (
        await db.execute(
            select(FeatureFlagOverride, Organization.name)
            .join(Organization, Organization.id == FeatureFlagOverride.organization_id)
            .where(FeatureFlagOverride.flag_id == flag.id)
            .order_by(FeatureFlagOverride.created_at.desc())
        )
    ).all()
    return [(override, org_name) for override, org_name in rows]


async def is_feature_enabled(db: AsyncSession, *, key: str, organization_id: uuid.UUID | None = None) -> bool:
    """Public helper other modules can use: `if await is_feature_enabled(db, key='x', organization_id=org.id): ...`"""
    flag = (await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))).scalar_one_or_none()
    if not flag:
        return False
    if organization_id is not None:
        override = (
            await db.execute(
                select(FeatureFlagOverride).where(
                    FeatureFlagOverride.flag_id == flag.id, FeatureFlagOverride.organization_id == organization_id
                )
            )
        ).scalar_one_or_none()
        if override is not None:
            return override.is_enabled
    return flag.is_enabled_globally


async def create_abuse_report(db: AsyncSession, *, organization_id: uuid.UUID, reason: str, reported_by_user_id: uuid.UUID | None) -> AbuseReport:
    report = AbuseReport(organization_id=organization_id, reason=reason, reported_by_user_id=reported_by_user_id)
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def list_abuse_reports(db: AsyncSession, *, status_filter: str | None = None) -> list[AbuseReport]:
    query = select(AbuseReport).order_by(AbuseReport.created_at.desc())
    if status_filter:
        query = query.where(AbuseReport.status == status_filter)
    return list((await db.execute(query)).scalars().all())


async def admin_search_delivery_jobs(
    db: AsyncSession, *, organization_id: uuid.UUID | None = None, status_filter: str | None = None, limit: int = 50, offset: int = 0
) -> list[DeliveryJob]:
    """
    Deliberately NOT scoped to a single organization by default -- this is the
    "global logs" admin feature and is only reachable behind require_platform_admin.
    Every other logs/search function in this codebase (Phase 3h) DOES scope to one
    org; this function is the one intentional, clearly-marked exception.
    """
    query = select(DeliveryJob).where(DeliveryJob.deleted_at.is_(None)).order_by(DeliveryJob.created_at.desc()).limit(limit).offset(offset)
    if organization_id is not None:
        query = query.where(DeliveryJob.organization_id == organization_id)
    if status_filter is not None:
        query = query.where(DeliveryJob.status == status_filter)
    return list((await db.execute(query)).scalars().all())


async def resolve_abuse_report(
    db: AsyncSession, *, report_id: uuid.UUID, new_status: str, resolution_notes: str | None,
    actor_user_id: uuid.UUID, ip_address: str | None,
) -> AbuseReport:
    report = (await db.execute(select(AbuseReport).where(AbuseReport.id == report_id))).scalar_one_or_none()
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Abuse report not found")

    report.status = new_status
    report.resolution_notes = resolution_notes
    if new_status in (AbuseReportStatus.RESOLVED.value, AbuseReportStatus.DISMISSED.value):
        report.resolved_at = datetime.now(timezone.utc)

    await audit_service.record(
        db, organization_id=report.organization_id, actor_user_id=actor_user_id, action=AuditAction.ADMIN_ABUSE_REPORT_RESOLVED,
        resource_type="abuse_report", resource_id=str(report.id), metadata={"status": new_status}, ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(report)
    return report
