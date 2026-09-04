from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Organization
from app.modules.delivery.models import DeliveryAttempt, DeliveryJob


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
