import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role
from app.modules.logs import service
from app.modules.logs.schemas import DeliveryLogEntryOut

router = APIRouter(prefix="/logs", tags=["delivery-logs"])


def _to_out(job) -> DeliveryLogEntryOut:
    return DeliveryLogEntryOut(
        id=job.id,
        event_id=job.event_id,
        endpoint_id=job.endpoint_id,
        event_type=job.event.event_type if job.event else "",
        environment=job.event.environment if job.event else "",
        request_id=job.event.request_id if job.event else "",
        status=job.status,
        attempt_number=job.attempt_number,
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
