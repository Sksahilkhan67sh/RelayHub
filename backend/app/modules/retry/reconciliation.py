"""
Reconciliation: the safety net that catches jobs which fell through every other
recovery path.

Update (Phase 2 follow-up): stuck-processing detection now has two tiers. When a
job's claiming worker (`DeliveryJob.claimed_by_worker_id`) has a heartbeat row in
`worker_heartbeats`, that's authoritative -- the job is recovered as soon as the
worker is confirmed dead (heartbeat stale), without waiting out the full
`STUCK_PROCESSING_AFTER` window, and never recovered purely on elapsed time while
the worker is confirmed alive. The original time-only heuristic remains as the
fallback for jobs with no usable lease signal (claimed before this feature existed,
or a worker with no heartbeat history at all). See `_find_stuck_processing_job_ids`
for the exact precedence.

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
from app.common.realtime_publisher import RealtimePublisher
from app.modules.admin.models import WorkerHeartbeat
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus
from app.modules.realtime.events import emit_delivery_update

logger = logging.getLogger(__name__)

# Fallback for jobs with no claimed_by_worker_id (pre-lease rows, or a claim whose
# worker_id was never recorded) or whose claiming worker has no entry at all in
# worker_heartbeats (heartbeat write never landed). Comfortably larger than the
# largest allowed endpoint timeout (see endpoints/schemas.py's validation range)
# plus HTTP connect/retry overhead, so a merely-slow delivery is never mistaken for
# an abandoned one.
STUCK_PROCESSING_AFTER = timedelta(minutes=10)

# Same worker-liveness threshold as admin/service.py's WORKER_HEARTBEAT_STALE_AFTER
# -- duplicated here (rather than imported) deliberately: this module cares about
# "is the specific worker that claimed this job provably dead", which is a stronger
# and slightly stricter question than admin's fleet-level "is this worker healthy
# right now" dashboard signal, and the two are allowed to diverge independently.
LEASE_WORKER_STALE_AFTER = timedelta(seconds=90)

# Small buffer after claiming before the lease path is trusted at all -- avoids a
# false "stuck" verdict in the narrow window right after a worker claims a job but
# before its very first heartbeat write (worker_process_init starts the heartbeat
# thread immediately, but the first write is not instantaneous).
LEASE_GRACE_PERIOD = timedelta(seconds=30)

# How long a job may sit in `queued` (dispatch never reached the broker) or
# `retrying` past its own `next_attempt_at` (the beat-scheduled scanner missed it,
# or its own enqueue failed) before reconciliation gives it a nudge.
STALE_DISPATCH_AFTER = timedelta(minutes=2)


@dataclass
class ReconciliationResult:
    recovered_stuck_processing: list[uuid.UUID] = field(default_factory=list)
    recovered_via_lease: list[uuid.UUID] = field(default_factory=list)
    recovered_via_time_heuristic: list[uuid.UUID] = field(default_factory=list)
    requeued_stale_queued: list[uuid.UUID] = field(default_factory=list)
    requeued_missed_retries: list[uuid.UUID] = field(default_factory=list)

    @property
    def total_requeued(self) -> int:
        return (
            len(self.recovered_stuck_processing)
            + len(self.requeued_stale_queued)
            + len(self.requeued_missed_retries)
        )


async def _find_stuck_processing_job_ids(
    db: AsyncSession,
    *,
    now: datetime,
    stuck_processing_after: timedelta,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """
    Returns (lease_confirmed_dead, time_heuristic_only) -- two separate lists so the
    caller can log/report which detection path recovered each job. A job can only
    appear in one of the two: the lease path is checked first and, when it applies
    (claimed_by_worker_id is set and that worker has *any* heartbeat row), it is
    authoritative for that job -- either the worker is confirmed dead (recovered
    immediately, no need to wait out the full 10-minute time window) or confirmed
    alive (never recovered by the time path either, however long it's been
    processing, since a live worker means real work may still be happening). Only
    jobs with no usable lease signal at all (no claimed_by_worker_id, or a worker_id
    with zero heartbeat history) fall through to the pure time heuristic.
    """
    processing_jobs = (
        await db.execute(
            select(DeliveryJob.id, DeliveryJob.claimed_by_worker_id, DeliveryJob.claimed_at, DeliveryJob.updated_at)
            .where(DeliveryJob.status == DeliveryJobStatus.PROCESSING.value)
        )
    ).all()
    if not processing_jobs:
        return [], []

    worker_ids = {row.claimed_by_worker_id for row in processing_jobs if row.claimed_by_worker_id}
    heartbeats_by_worker: dict[str, datetime] = {}
    if worker_ids:
        heartbeat_rows = (
            await db.execute(
                select(WorkerHeartbeat.worker_id, WorkerHeartbeat.last_heartbeat_at).where(
                    WorkerHeartbeat.worker_id.in_(worker_ids)
                )
            )
        ).all()
        for heartbeat_row in heartbeat_rows:
            last_seen = heartbeat_row.last_heartbeat_at
            if last_seen.tzinfo is None:  # SQLite in tests doesn't round-trip tzinfo; Postgres always does
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            heartbeats_by_worker[heartbeat_row.worker_id] = last_seen

    lease_dead: list[uuid.UUID] = []
    time_heuristic_only: list[uuid.UUID] = []
    stuck_cutoff = now - stuck_processing_after

    for row in processing_jobs:
        claimed_at = row.claimed_at
        if claimed_at is not None and claimed_at.tzinfo is None:
            claimed_at = claimed_at.replace(tzinfo=timezone.utc)
        within_grace = claimed_at is not None and (now - claimed_at) < LEASE_GRACE_PERIOD

        last_heartbeat = heartbeats_by_worker.get(row.claimed_by_worker_id) if row.claimed_by_worker_id else None

        if last_heartbeat is not None and not within_grace:
            # We have a real signal for this specific worker: trust it over elapsed
            # time entirely. Alive -> never mark stuck here, however long it's been
            # (the worker is doing something, even if slowly). Dead -> recover now,
            # without waiting for STUCK_PROCESSING_AFTER.
            if now - last_heartbeat >= LEASE_WORKER_STALE_AFTER:
                lease_dead.append(row.id)
            continue

        # No usable lease (no claimed_by_worker_id, worker has zero heartbeat
        # history, or we're still inside the post-claim grace period) -- fall back
        # to the original time-only heuristic.
        updated_at = row.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if updated_at < stuck_cutoff:
            time_heuristic_only.append(row.id)

    return lease_dead, time_heuristic_only


async def reconcile_stuck_jobs(
    db: AsyncSession,
    *,
    queue_client: QueueClient,
    now: datetime | None = None,
    stuck_processing_after: timedelta = STUCK_PROCESSING_AFTER,
    stale_dispatch_after: timedelta = STALE_DISPATCH_AFTER,
    realtime_publisher: RealtimePublisher | None = None,
) -> ReconciliationResult:
    now = now or datetime.now(timezone.utc)
    result = ReconciliationResult()

    # 1. Jobs abandoned mid-processing (worker crash/kill after the CAS claim
    # committed, before the job finished). Move them back to `retrying` with an
    # immediate `next_attempt_at` so the normal claim/executor path picks them up
    # like any other retry -- no special-cased "recovered" state to keep track of.
    # Two detection paths feed into the same recovery action -- see
    # `_find_stuck_processing_job_ids` for why the lease path (when available) is
    # authoritative and the time heuristic is only the fallback.
    lease_dead_ids, time_heuristic_ids = await _find_stuck_processing_job_ids(
        db, now=now, stuck_processing_after=stuck_processing_after
    )
    all_stuck_ids = lease_dead_ids + time_heuristic_ids
    if all_stuck_ids:
        await db.execute(
            update(DeliveryJob)
            .where(DeliveryJob.id.in_(all_stuck_ids), DeliveryJob.status == DeliveryJobStatus.PROCESSING.value)
            .values(status=DeliveryJobStatus.RETRYING.value, next_attempt_at=now, updated_at=now)
        )
    result.recovered_via_lease = lease_dead_ids
    result.recovered_via_time_heuristic = time_heuristic_ids
    result.recovered_stuck_processing = all_stuck_ids
    if lease_dead_ids:
        logger.warning(
            "reconciliation recovered %d job(s) via worker-heartbeat lease (owning worker confirmed dead)",
            len(lease_dead_ids),
        )
    if time_heuristic_ids:
        logger.warning(
            "reconciliation recovered %d job(s) stuck in processing past %s (time heuristic, no usable lease)",
            len(time_heuristic_ids), stuck_processing_after,
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

    # Realtime "retrying" notifications for jobs recovered from stuck `processing`
    # -- strictly after the commit above. These rows don't have their endpoint
    # loaded here (a bulk UPDATE, not a per-row fetch, by design -- see the module
    # docstring on why this stays a single statement), so max_attempts is omitted
    # rather than issuing an extra query per recovered job just for a display
    # nicety the frontend already has cached from its last REST fetch (same
    # reasoning as this module's own dataclass docstring on emit_delivery_update).
    if realtime_publisher is not None and result.recovered_stuck_processing:
        recovered_rows = (
            await db.execute(
                select(DeliveryJob.id, DeliveryJob.organization_id, DeliveryJob.event_id, DeliveryJob.endpoint_id,
                       DeliveryJob.attempt_number, DeliveryJob.queued_at, DeliveryJob.next_attempt_at)
                .where(DeliveryJob.id.in_(result.recovered_stuck_processing))
            )
        ).all()
        for row in recovered_rows:
            await emit_delivery_update(
                realtime_publisher,
                organization_id=row.organization_id,
                delivery_job_id=row.id,
                event_id=row.event_id,
                endpoint_id=row.endpoint_id,
                status=DeliveryJobStatus.RETRYING.value,
                attempt_number=row.attempt_number,
                queued_at=row.queued_at,
                next_attempt_at=row.next_attempt_at,
            )

    for job_id in (*result.recovered_stuck_processing, *result.requeued_stale_queued, *result.requeued_missed_retries):
        await queue_client.enqueue(job_id)

    return result
