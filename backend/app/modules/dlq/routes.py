import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.queue_client import QueueClient, get_queue_client
from app.common.realtime_publisher import RealtimePublisher, get_realtime_publisher
from app.common.route_rate_limit import org_rate_limit
from app.db.session import get_db
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role
from app.modules.dlq import service
from app.modules.dlq.schemas import BulkRetryRequest, BulkRetryResponse, DeadLetterJobOut, RetryDeadLetterResponse
from app.modules.retry.schedule import DEFAULT_MAX_ATTEMPTS

router = APIRouter(prefix="/dlq", tags=["dead-letter-queue"])

# Replay is the most resource-amplifying authenticated operation in the API: a
# single bulk-retry call re-enqueues up to 500 delivery jobs (see
# BulkRetryRequest's max_length), each of which becomes real outbound HTTP work
# for a delivery worker. Before Phase 4 these endpoints had no rate limit at
# all, so a caller (or a buggy client in a loop) could saturate the delivery
# queue with replays. Limits are per-organization and generous enough not to
# interfere with legitimate incident recovery -- an operator working through a
# DLQ backlog after an outage will not hit these -- while bounding the worst
# case. Export is separately limited because it scans and serializes the whole
# DLQ for an org into CSV in one request.
DLQ_REPLAY_LIMIT = 60
DLQ_REPLAY_WINDOW_SECONDS = 60
DLQ_BULK_REPLAY_LIMIT = 10
DLQ_BULK_REPLAY_WINDOW_SECONDS = 60
DLQ_EXPORT_LIMIT = 10
DLQ_EXPORT_WINDOW_SECONDS = 60


def _to_out(job) -> DeadLetterJobOut:
    latest = job.attempts[-1] if job.attempts else None
    effective_max_attempts = (
        job.endpoint.max_retry_attempts if job.endpoint and job.endpoint.max_retry_attempts is not None else DEFAULT_MAX_ATTEMPTS
    )
    return DeadLetterJobOut(
        id=job.id,
        event_id=job.event_id,
        endpoint_id=job.endpoint_id,
        event_type=job.event.event_type if job.event else "",
        payload=job.event.payload if job.event else {},
        attempt_number=job.attempt_number,
        max_attempts=effective_max_attempts,
        queued_at=job.queued_at,
        completed_at=job.completed_at,
        last_error_category=latest.error_category if latest else None,
        last_error_message=latest.error_message if latest else None,
        attempts=list(job.attempts),
    )


@router.get("", response_model=list[DeadLetterJobOut])
async def list_dead_letter_jobs(
    endpoint_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    jobs = await service.list_dead_letter_jobs(
        db, organization_id=auth.organization_id, endpoint_id=endpoint_id, limit=limit, offset=offset
    )
    return [_to_out(j) for j in jobs]


@router.get("/export")
async def export_dead_letter_jobs(
    response: Response,
    endpoint_id: uuid.UUID | None = Query(default=None),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(
        org_rate_limit("dlq-export", limit=DLQ_EXPORT_LIMIT, window_seconds=DLQ_EXPORT_WINDOW_SECONDS)
    ),
):
    csv_content = await service.export_dead_letter_jobs_csv(db, organization_id=auth.organization_id, endpoint_id=endpoint_id)
    # NOTE: this handler constructs its own Response rather than using the
    # injected `response` object, so rate-limit headers set by the
    # org_rate_limit dependency would be discarded. Carry them over
    # explicitly. (The 429 path is unaffected either way -- that raises an
    # HTTPException with its own headers before this handler ever runs.)
    headers = {"Content-Disposition": "attachment; filename=relayhub_dead_letter_export.csv"}
    headers.update({k: v for k, v in response.headers.items() if k.lower().startswith("x-ratelimit-")})
    return Response(content=csv_content, media_type="text/csv", headers=headers)


@router.get("/{job_id}", response_model=DeadLetterJobOut)
async def get_dead_letter_job(
    job_id: uuid.UUID, auth: AuthContext = Depends(require_role(Role.VIEWER)), db: AsyncSession = Depends(get_db)
):
    job = await service.get_dead_letter_job(db, organization_id=auth.organization_id, job_id=job_id)
    return _to_out(job)


@router.post("/{job_id}/retry", response_model=RetryDeadLetterResponse)
async def retry_dead_letter_job(
    job_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
    queue_client: QueueClient = Depends(get_queue_client),
    realtime_publisher: RealtimePublisher = Depends(get_realtime_publisher),
    _rate_limit: None = Depends(
        org_rate_limit("dlq-replay", limit=DLQ_REPLAY_LIMIT, window_seconds=DLQ_REPLAY_WINDOW_SECONDS)
    ),
):
    job = await service.retry_dead_letter_job(
        db,
        organization_id=auth.organization_id,
        job_id=job_id,
        actor_user_id=auth.user_id,
        queue_client=queue_client,
        ip_address=request.client.host if request.client else None,
        realtime_publisher=realtime_publisher,
    )
    return RetryDeadLetterResponse(id=job.id, status=job.status)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dead_letter_job(
    job_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_dead_letter_job(
        db,
        organization_id=auth.organization_id,
        job_id=job_id,
        actor_user_id=auth.user_id,
        ip_address=request.client.host if request.client else None,
    )


@router.post("/bulk-retry", response_model=BulkRetryResponse)
async def bulk_retry_dead_letter_jobs(
    payload: BulkRetryRequest,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
    queue_client: QueueClient = Depends(get_queue_client),
    realtime_publisher: RealtimePublisher = Depends(get_realtime_publisher),
    _rate_limit: None = Depends(
        org_rate_limit("dlq-bulk-replay", limit=DLQ_BULK_REPLAY_LIMIT, window_seconds=DLQ_BULK_REPLAY_WINDOW_SECONDS)
    ),
):
    retried, skipped = await service.bulk_retry_dead_letter_jobs(
        db,
        organization_id=auth.organization_id,
        job_ids=payload.job_ids,
        actor_user_id=auth.user_id,
        queue_client=queue_client,
        ip_address=request.client.host if request.client else None,
        realtime_publisher=realtime_publisher,
    )
    return BulkRetryResponse(retried=retried, skipped=skipped)
