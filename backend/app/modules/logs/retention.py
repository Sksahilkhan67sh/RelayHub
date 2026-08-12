"""
Retention cleanup per spec: Free=7 days, Starter=30, Pro=90 (configurable),
Enterprise=custom. Organization.log_retention_days holds the effective value
(defaulted to 30 today; Phase 3l's billing module will set it from the org's real
plan on subscribe/upgrade/downgrade).

Only terminal-state jobs (success, failed, dead_letter) are ever purged -- a job still
queued/retrying is never deleted regardless of age, since that would silently drop a
delivery that's still legitimately in flight.

DeliveryAttempt rows cascade-delete via the FK's ondelete=CASCADE; Event rows are
deliberately NOT purged here -- they remain for idempotency-key lookups and are a
separate, smaller retention concern.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Organization
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus

TERMINAL_STATUSES = [DeliveryJobStatus.SUCCESS.value, DeliveryJobStatus.FAILED.value, DeliveryJobStatus.DEAD_LETTER.value]


async def cleanup_expired_delivery_logs(db: AsyncSession, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    total_deleted = 0

    orgs = (await db.execute(select(Organization).where(Organization.deleted_at.is_(None)))).scalars().all()
    for org in orgs:
        cutoff = now - timedelta(days=org.log_retention_days)
        result = await db.execute(
            delete(DeliveryJob).where(
                DeliveryJob.organization_id == org.id,
                DeliveryJob.status.in_(TERMINAL_STATUSES),
                DeliveryJob.completed_at.is_not(None),
                DeliveryJob.completed_at < cutoff,
            )
        )
        total_deleted += result.rowcount or 0

    await db.commit()
    return total_deleted
