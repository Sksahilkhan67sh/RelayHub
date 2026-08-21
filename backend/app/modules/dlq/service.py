from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.queue_client import QueueClient
from app.modules.audit import service as audit_service
from app.modules.audit.models import AuditAction
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus

logger = logging.getLogger(__name__)


def _latest_attempt(job: DeliveryJob):
    return job.attempts[-1] if job.attempts else None


async def list_dead_letter_jobs(
    db: AsyncSession, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID | None = None, limit: int = 50, offset: int = 0
) -> list[DeliveryJob]:
    query = (
        select(DeliveryJob)
        .options(selectinload(DeliveryJob.attempts), selectinload(DeliveryJob.event), selectinload(DeliveryJob.endpoint))
        .where(
            DeliveryJob.organization_id == organization_id,
            DeliveryJob.status == DeliveryJobStatus.DEAD_LETTER.value,
            DeliveryJob.deleted_at.is_(None),
        )
        .order_by(DeliveryJob.completed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if endpoint_id is not None:
        query = query.where(DeliveryJob.endpoint_id == endpoint_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def _get_dlq_job_or_404(db: AsyncSession, *, organization_id: uuid.UUID, job_id: uuid.UUID) -> DeliveryJob:
    job = (
        await db.execute(
            select(DeliveryJob)
            .options(selectinload(DeliveryJob.attempts), selectinload(DeliveryJob.event), selectinload(DeliveryJob.endpoint))
            .where(
                DeliveryJob.id == job_id,
                DeliveryJob.organization_id == organization_id,
                DeliveryJob.status == DeliveryJobStatus.DEAD_LETTER.value,
                DeliveryJob.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Dead letter job not found")
    return job


async def get_dead_letter_job(db: AsyncSession, *, organization_id: uuid.UUID, job_id: uuid.UUID) -> DeliveryJob:
    return await _get_dlq_job_or_404(db, organization_id=organization_id, job_id=job_id)


async def retry_dead_letter_job(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    job_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    queue_client: QueueClient,
    ip_address: str | None,
) -> DeliveryJob:
    job = await _get_dlq_job_or_404(db, organization_id=organization_id, job_id=job_id)

    # A manual retry from the DLQ is a deliberate customer decision to give this
    # delivery a fresh chance -- reset the attempt counter so it gets the FULL retry
    # schedule again on subsequent failures, not just one more shot before re-DLQ'ing.
    job.status = DeliveryJobStatus.QUEUED.value
    job.attempt_number = 0
    job.next_attempt_at = None
    job.completed_at = None
    job.queued_at = datetime.now(timezone.utc)

    await audit_service.record(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction.DLQ_JOB_RETRIED,
        resource_type="delivery_job",
        resource_id=str(job.id),
        metadata={},
        ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(job, attribute_names=["attempts"])

    # The status flip to `queued` above is already durably committed -- a broker
    # failure here must not surface as a failed retry request (the retry DID
    # happen, from the DB's point of view) and must not be left silently
    # undispatched: reconcile_stuck_jobs' stale-`queued` pass will pick this row up
    # within STALE_DISPATCH_AFTER if the immediate dispatch below fails. Same
    # reasoning as events/service.py's publish_event fix.
    try:
        await queue_client.enqueue(job.id)
    except Exception:  # noqa: BLE001 - broker outage must not fail an already-committed DLQ retry
        logger.exception(
            "queue dispatch failed for DLQ retry of delivery_job=%s -- job remains queued in the "
            "database and will be picked up by reconciliation",
            job.id,
        )
    return job


async def delete_dead_letter_job(
    db: AsyncSession, *, organization_id: uuid.UUID, job_id: uuid.UUID, actor_user_id: uuid.UUID, ip_address: str | None
) -> None:
    job = await _get_dlq_job_or_404(db, organization_id=organization_id, job_id=job_id)
    job.deleted_at = datetime.now(timezone.utc)

    await audit_service.record(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction.DLQ_JOB_DELETED,
        resource_type="delivery_job",
        resource_id=str(job.id),
        metadata={},
        ip_address=ip_address,
    )
    await db.commit()


async def bulk_retry_dead_letter_jobs(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    job_ids: list[uuid.UUID],
    actor_user_id: uuid.UUID,
    queue_client: QueueClient,
    ip_address: str | None,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    retried: list[uuid.UUID] = []
    skipped: list[uuid.UUID] = []

    for job_id in job_ids:
        job = (
            await db.execute(
                select(DeliveryJob).where(
                    DeliveryJob.id == job_id,
                    DeliveryJob.organization_id == organization_id,
                    DeliveryJob.status == DeliveryJobStatus.DEAD_LETTER.value,
                    DeliveryJob.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if not job:
            skipped.append(job_id)
            continue

        job.status = DeliveryJobStatus.QUEUED.value
        job.attempt_number = 0
        job.next_attempt_at = None
        job.completed_at = None
        job.queued_at = datetime.now(timezone.utc)
        retried.append(job_id)

    await audit_service.record(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction.DLQ_BULK_RETRIED,
        resource_type="delivery_job",
        resource_id=None,
        metadata={"retried_count": len(retried), "skipped_count": len(skipped)},
        ip_address=ip_address,
    )
    await db.commit()

    for job_id in retried:
        try:
            await queue_client.enqueue(job_id)
        except Exception:  # noqa: BLE001 - one broker failure must not abort dispatch of the rest of this
            # bulk retry, and the already-committed `queued` rows are safely picked up by reconciliation
            # even if this dispatch never succeeds.
            logger.exception("queue dispatch failed for bulk DLQ retry of delivery_job=%s", job_id)

    return retried, skipped


async def export_dead_letter_jobs_csv(
    db: AsyncSession, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID | None = None
) -> str:
    jobs = await list_dead_letter_jobs(db, organization_id=organization_id, endpoint_id=endpoint_id, limit=10000, offset=0)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "delivery_job_id", "event_id", "event_type", "endpoint_id", "attempt_number",
            "queued_at", "completed_at", "last_error_category", "last_error_message",
        ]
    )
    for job in jobs:
        latest = _latest_attempt(job)
        writer.writerow(
            [
                str(job.id),
                str(job.event_id),
                job.event.event_type if job.event else "",
                str(job.endpoint_id),
                job.attempt_number,
                job.queued_at.isoformat() if job.queued_at else "",
                job.completed_at.isoformat() if job.completed_at else "",
                latest.error_category if latest else "",
                latest.error_message if latest else "",
            ]
        )
    return buffer.getvalue()
