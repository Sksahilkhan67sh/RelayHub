import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role
from app.modules.delivery import query_service
from app.modules.delivery.models import DeliveryJob
from app.modules.delivery.schemas import DeliveryJobOut

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


def _to_out(job: DeliveryJob) -> DeliveryJobOut:
    return DeliveryJobOut(
        id=job.id,
        event_id=job.event_id,
        endpoint_id=job.endpoint_id,
        event_type=job.event.event_type if job.event else "",
        payload=job.event.payload if job.event else {},
        status=job.status,
        attempt_number=job.attempt_number,
        queued_at=job.queued_at,
        next_attempt_at=job.next_attempt_at,
        completed_at=job.completed_at,
        attempts=list(job.attempts),
    )


@router.get("/{job_id}", response_model=DeliveryJobOut)
async def get_delivery_job(
    job_id: uuid.UUID, auth: AuthContext = Depends(require_role(Role.VIEWER)), db: AsyncSession = Depends(get_db)
):
    job = await query_service.get_delivery_job(db, organization_id=auth.organization_id, job_id=job_id)
    return _to_out(job)


@router.get("/by-event/{event_id}", response_model=list[DeliveryJobOut])
async def list_deliveries_for_event(
    event_id: uuid.UUID, auth: AuthContext = Depends(require_role(Role.VIEWER)), db: AsyncSession = Depends(get_db)
):
    jobs = await query_service.list_delivery_jobs_for_event(db, organization_id=auth.organization_id, event_id=event_id)
    return [_to_out(j) for j in jobs]
