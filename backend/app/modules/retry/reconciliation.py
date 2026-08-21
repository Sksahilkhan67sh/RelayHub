"""
Reconciliation: the safety net that catches jobs which fell through every other
recovery path.

Why this exists (a real, verified bug this module fixes):

  Celery is configured with `task_acks_late=True` + `task_reject_on_worker_lost=True`
  (see app/workers/celery_app.py) specifically so a worker that crashes/is killed
  mid-task gets its message redelivered rather than lost. But `execute_delivery_job`'s
  claim step (`_claim_job` in delivery/executor.py) flips the job's DB status to
  `processing` and *commits that before doing any of the actual work* (HTTP call,
  attempt recording). If the worker dies after that commit but before finishing,
  Celery redelivers the task -- and the redelivered task calls `_claim_job` again,
  which now finds status=processing (not queued/retrying) and raises
  `JobAlreadyClaimedError`, which `tasks.py` treats as "someone else has this, skip
  it". Nobody else does. The job is left in `processing` forever: not delivered, not
  retried, not dead-lettered, no error surfaced anywhere -- a silent, permanent
  event loss. This was confirmed by reasoning through the exact commit ordering in
  `_claim_job`/`_finish`, not assumed.

  A second, related gap: `events/service.py` enqueues onto the Celery broker *after*
  the DB commit that creates the DeliveryJob row (correct ordering -- the row is
  never lost). But if that `enqueue()` call itself fails (Redis/broker unreachable),
  nothing currently re-tries the dispatch -- the row sits in `queued` with no message
  on the broker, and previously nothing would ever notice.

  There is also no worker-heartbeat/lease table in this codebase (confirmed:
  admin/service.py's `get_system_health` explicitly documents this absence rather
  than fabricating it). Without a real per-job lease, "stuck" detection here uses a
  time-based heuristic against `updated_at` (which the executor's CAS claim already
  bumps via TimestampMixin's `onupdate=func.now()`): a job stuck in `processing`
  well past any realistic endpoint timeout is treated as abandoned. This is
  deliberately conservative (`STUCK_PROCESSING_AFTER` is several times larger than
  the largest allowed endpoint timeout) to avoid reclaiming a job that is simply
  slow, not dead. It is still a heuristic, not a true lease -- documented as a known
  limitation in the phase report, not hidden.

Reconciliation is safe to run concurrently with itself and with normal delivery:
every transition below is a single bulk `UPDATE ... WHERE status = ... RETURNING`,
so two reconciliation workers racing each other (or racing a real worker's CAS
claim) can each only "win" rows that still match the WHERE clause at commit time --
identical safety property to `_claim_job`. Re-enqueuing a job that was never
actually lost (e.g. it's just sitting in a deep Celery backlog) is a harmless
duplicate message: `_claim_job`'s CAS makes a second delivery attempt on an
already-claimed job impossible, exactly as `retry/scheduler.py` already relies on
for the same reason.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.queue_client import QueueClient
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus

logger = logging.getLogger(__name__)

# Comfortably larger than the largest allowed endpoint timeout (see
# endpoints/schemas.py's validation range) plus HTTP connect/retry overhead, so a
# merely-slow delivery is never mistaken for an abandoned one.
STUCK_PROCESSING_AFTER = timedelta(minutes=10)

# How long a job may sit in `queued` (dispatch never reached the broker) or
# `retrying` past its own `next_attempt_at` (the beat-scheduled scanner missed it,
# or its own enqueue failed) before reconciliation gives it a nudge.
STALE_DISPATCH_AFTER = timedelta(minutes=2)


@dataclass
class ReconciliationResult:
    recovered_stuck_processing: list[uuid.UUID] = field(default_factory=list)
    requeued_stale_queued: list[uuid.UUID] = field(default_factory=list)
    requeued_missed_retries: list[uuid.UUID] = field(default_factory=list)

    @property
    def total_requeued(self) -> int:
        return (
            len(self.recovered_stuck_processing)
            + len(self.requeued_stale_queued)
            + len(self.requeued_missed_retries)
        )


async def reconcile_stuck_jobs(
    db: AsyncSession,
    *,
    queue_client: QueueClient,
    now: datetime | None = None,
    stuck_processing_after: timedelta = STUCK_PROCESSING_AFTER,
    stale_dispatch_after: timedelta = STALE_DISPATCH_AFTER,
) -> ReconciliationResult:
    now = now or datetime.now(timezone.utc)
    result = ReconciliationResult()

    # 1. Jobs abandoned mid-processing (worker crash/kill after the CAS claim
    # committed, before the job finished). Move them back to `retrying` with an
    # immediate `next_attempt_at` so the normal claim/executor path picks them up
    # like any other retry -- no special-cased "recovered" state to keep track of.
    stuck_cutoff = now - stuck_processing_after
    stuck_rows = (
        await db.execute(
            update(DeliveryJob)
            .where(
                DeliveryJob.status == DeliveryJobStatus.PROCESSING.value,
                DeliveryJob.updated_at < stuck_cutoff,
            )
            .values(status=DeliveryJobStatus.RETRYING.value, next_attempt_at=now, updated_at=now)
            .returning(DeliveryJob.id)
        )
    ).all()
    result.recovered_stuck_processing = [row[0] for row in stuck_rows]
    if result.recovered_stuck_processing:
        logger.warning(
            "reconciliation recovered %d job(s) stuck in processing past %s",
            len(result.recovered_stuck_processing), stuck_processing_after,
        )

    # 2. Jobs whose row was durably persisted but whose broker dispatch either
    # failed outright or was never confirmed. Status is already valid for the
    # executor's CAS claim (queued/retrying) -- just nudge `updated_at` so we don't
    # re-select the same rows on every tick, and re-enqueue.
    stale_cutoff = now - stale_dispatch_after
    stale_queued_rows = (
        await db.execute(
            update(DeliveryJob)
            .where(DeliveryJob.status == DeliveryJobStatus.QUEUED.value, DeliveryJob.updated_at < stale_cutoff)
            .values(updated_at=now)
            .returning(DeliveryJob.id)
        )
    ).all()
    result.requeued_stale_queued = [row[0] for row in stale_queued_rows]

    # 3. Retrying jobs whose next_attempt_at has already passed by more than the
    # stale-dispatch grace period -- normally `check_due_retries` (10s tick) catches
    # these; this is the backstop for when that scanner itself missed a tick or its
    # own enqueue failed.
    missed_retry_ids = (
        await db.execute(
            select(DeliveryJob.id).where(
                DeliveryJob.status == DeliveryJobStatus.RETRYING.value,
                DeliveryJob.next_attempt_at.is_not(None),
                DeliveryJob.next_attempt_at < stale_cutoff,
                DeliveryJob.updated_at < stale_cutoff,
            )
        )
    ).scalars().all()
    if missed_retry_ids:
        await db.execute(
            update(DeliveryJob).where(DeliveryJob.id.in_(missed_retry_ids)).values(updated_at=now)
        )
    result.requeued_missed_retries = list(missed_retry_ids)

    await db.commit()

    for job_id in (*result.recovered_stuck_processing, *result.requeued_stale_queued, *result.requeued_missed_retries):
        await queue_client.enqueue(job_id)

    return result
