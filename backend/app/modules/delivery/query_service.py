from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.delivery.models import DeliveryJob


async def get_delivery_job(db: AsyncSession, *, organization_id: uuid.UUID, job_id: uuid.UUID) -> DeliveryJob:
    job = (
        await db.execute(
            select(DeliveryJob)
            .options(selectinload(DeliveryJob.attempts), selectinload(DeliveryJob.event), selectinload(DeliveryJob.endpoint))
            .where(DeliveryJob.id == job_id, DeliveryJob.organization_id == organization_id, DeliveryJob.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Delivery job not found")
    return job


async def list_delivery_jobs_for_event(db: AsyncSession, *, organization_id: uuid.UUID, event_id: uuid.UUID) -> list[DeliveryJob]:
    result = await db.execute(
        select(DeliveryJob)
        .options(selectinload(DeliveryJob.attempts), selectinload(DeliveryJob.event), selectinload(DeliveryJob.endpoint))
        .where(
            DeliveryJob.organization_id == organization_id,
            DeliveryJob.event_id == event_id,
            DeliveryJob.deleted_at.is_(None),
        )
        .order_by(DeliveryJob.created_at.desc())
    )
    return list(result.scalars().all())
