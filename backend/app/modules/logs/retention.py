import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Organization, Role
from app.modules.delivery.models import DeliveryAttempt, DeliveryJob
from app.modules.logs import service
from app.modules.logs.schemas import DeliveryLogEntryOut
from app.modules.retry.schedule import DEFAULT_MAX_ATTEMPTS

router = APIRouter(prefix="/logs", tags=["delivery-logs"])


async def cleanup_expired_delivery_logs(db: AsyncSession) -> int:
    """
    Delete delivery_jobs (and their delivery_attempts) that have reached a terminal
    state -- i.e. `completed_at` is set -- and are older than the owning
    organization's `log_retention_days` (set from the org's billing plan, see
    `billing/service.py`). Jobs still in flight (`completed_at` is None: queued,
    processing, retrying) are never touched, no matter how old `queued_at` is --
    only a job that has actually finished has a real "age" to retain.

    Retention is per-organization, not a single global cutoff, so this iterates
    organizations rather than filtering on one fixed interval.

    Backing the Celery beat task `cleanup_expired_delivery_logs`
    (app/workers/celery_app.py / app/workers/tasks.py). Explicitly deletes
    delivery_attempts first rather than relying on the DB-level ON DELETE CASCADE,
    since SQLite (used in tests/local dev) doesn't enforce FK cascades unless
    foreign_keys=ON is set, and this function needs identical behavior on both.

    Returns the number of delivery_jobs deleted.
    """
    total_deleted = 0
    orgs = (await db.execute(select(Organization.id, Organization.log_retention_days))).all()
    for org_id, retention_days in orgs:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        expired_ids = (
            await db.execute(
                select(DeliveryJob.id).where(
                    DeliveryJob.organization_id == org_id,
                    DeliveryJob.completed_at.isnot(None),
                    DeliveryJob.completed_at < cutoff,
                )
            )
        ).scalars().all()
        if not expired_ids:
            continue
        await db.execute(delete(DeliveryAttempt).where(DeliveryAttempt.delivery_job_id.in_(expired_ids)))
        result = await db.execute(delete(DeliveryJob).where(DeliveryJob.id.in_(expired_ids)))
        total_deleted += result.rowcount or 0

    await db.commit()
    return total_deleted


def _to_out(job) -> DeliveryLogEntryOut:
    effective_max_attempts = (
        job.endpoint.max_retry_attempts if job.endpoint and job.endpoint.max_retry_attempts is not None else DEFAULT_MAX_ATTEMPTS
    )
    return DeliveryLogEntryOut(
        id=job.id,
        event_id=job.event_id,
        endpoint_id=job.endpoint_id,
        event_type=job.event.event_type if job.event else "",
        environment=job.event.environment if job.event else "",
        request_id=job.event.request_id if job.event else "",
        status=job.status,
        attempt_number=job.attempt_number,
        max_attempts=effective_max_attempts,
        queued_at=job.queued_at,
        next_attempt_at=job.next_attempt_at,
        completed_at=job.completed_at,
        attempts=list(job.attempts),
    )


@router.get("", response_model=list[DeliveryLogEntryOut])
async def search_logs(
    endpoint_id: uuid.UUID | None = Query(default=None),
    status: list[str] | None = Query(default=None, description="One or more of: queued, processing, success, retrying, failed, dead_letter, pending"),
    event_type: str | None = Query(default=None),
    environment: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    worker_id: str | None = Query(default=None),
    queued_after: datetime | None = Query(default=None),
    queued_before: datetime | None = Query(default=None),
    min_latency_ms: int | None = Query(default=None, ge=0),
    max_latency_ms: int | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    jobs = await service.search_delivery_logs(
        db,
        organization_id=auth.organization_id,
        endpoint_id=endpoint_id,
        statuses=status,
        event_type=event_type,
        environment=environment,
        request_id=request_id,
        worker_id=worker_id,
        queued_after=queued_after,
        queued_before=queued_before,
        min_latency_ms=min_latency_ms,
        max_latency_ms=max_latency_ms,
        limit=limit,
        offset=offset,
    )
    return [_to_out(j) for j in jobs]


@router.get("/export")
async def export_logs(
    endpoint_id: uuid.UUID | None = Query(default=None),
    status: list[str] | None = Query(default=None, description="One or more of: queued, processing, success, retrying, failed, dead_letter, pending"),
    event_type: str | None = Query(default=None),
    environment: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    worker_id: str | None = Query(default=None),
    queued_after: datetime | None = Query(default=None),
    queued_before: datetime | None = Query(default=None),
    min_latency_ms: int | None = Query(default=None, ge=0),
    max_latency_ms: int | None = Query(default=None, ge=0),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    # Same filters as `search_logs` above, minus limit/offset -- an export is meant
    # to capture every matching delivery (up to service.EXPORT_MAX_ROWS), not one
    # page of them. Unlike /v1/dlq/export (dead-letter jobs only) or
    # /v1/insights/export (aggregated counts), this returns every individual
    # delivery job -- success, failed, retrying, dead_letter, etc. -- one row each.
    csv_content = await service.export_delivery_logs_csv(
        db,
        organization_id=auth.organization_id,
        endpoint_id=endpoint_id,
        statuses=status,
        event_type=event_type,
        environment=environment,
        request_id=request_id,
        worker_id=worker_id,
        queued_after=queued_after,
        queued_before=queued_before,
        min_latency_ms=min_latency_ms,
        max_latency_ms=max_latency_ms,
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=relayhub_delivery_logs.csv"},
    )
