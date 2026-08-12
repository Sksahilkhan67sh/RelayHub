from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.queue_client import QueueClient
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus


async def enqueue_due_retries(db: AsyncSession, *, queue_client: QueueClient, now: datetime | None = None) -> list[uuid.UUID]:
    """
    Finds delivery_jobs in status=retrying whose next_attempt_at has arrived and
    pushes their IDs back onto the queue so a worker picks them up.

    Deliberately does NOT flip status here -- leaving it as "retrying" means the
    executor's compare-and-set claim (queued/retrying -> processing) still works
    correctly even if this scanner runs more than once before a worker claims the
    job (e.g. two scheduler ticks close together): the second enqueue is a harmless
    duplicate message, not a duplicate delivery, because only one claim can succeed.
    """
    now = now or datetime.now(timezone.utc)
    result = await db.execute(
        select(DeliveryJob).where(
            DeliveryJob.status == DeliveryJobStatus.RETRYING.value,
            DeliveryJob.next_attempt_at.is_not(None),
            DeliveryJob.next_attempt_at <= now,
        )
    )
    due_jobs = result.scalars().all()
    for job in due_jobs:
        await queue_client.enqueue(job.id)
    return [job.id for job in due_jobs]
