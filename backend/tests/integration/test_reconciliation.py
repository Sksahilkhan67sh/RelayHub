"""
Regression tests for app/modules/retry/reconciliation.py.

Covers the specific bug this module fixes: a job abandoned in `processing` (worker
crash after the CAS claim committed but before finishing) is otherwise unrecoverable
forever, because Celery's redelivered task hits `_claim_job` a second time, finds
status=processing, and raises JobAlreadyClaimedError -- which tasks.py treats as
"someone else already has it", not as "recover this".
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.common.queue_client import InMemoryQueueClient
from app.modules.delivery.executor import JobAlreadyClaimedError, execute_delivery_job
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus
from app.modules.retry.reconciliation import reconcile_stuck_jobs
from tests.conftest import create_api_key, create_endpoint, register_and_get_token


async def _publish_and_get_job_id(client, db_session, unique_email) -> uuid.UUID:
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    publish_resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    return uuid.UUID(publish_resp.json()["delivery_jobs"][0]["id"])


@pytest.mark.asyncio
async def test_job_abandoned_in_processing_is_unrecoverable_without_reconciliation(client, unique_email, db_session):
    """
    Documents the bug in isolation: without reconciliation, a job stuck in
    `processing` (simulating a worker crash right after the CAS claim committed)
    stays claimed forever -- a second delivery attempt is rejected as
    "already claimed", not recovered.
    """
    job_id = await _publish_and_get_job_id(client, db_session, unique_email)

    # Simulate the CAS claim having committed, then the worker dying before _finish.
    await db_session.execute(
        update(DeliveryJob).where(DeliveryJob.id == job_id).values(status=DeliveryJobStatus.PROCESSING.value)
    )
    await db_session.commit()

    with pytest.raises(JobAlreadyClaimedError):
        await execute_delivery_job(db_session, job_id=job_id)

    job = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
    assert job.status == DeliveryJobStatus.PROCESSING.value  # still stuck -- this is the bug


@pytest.mark.asyncio
async def test_reconciliation_recovers_job_stuck_in_processing(client, unique_email, db_session):
    job_id = await _publish_and_get_job_id(client, db_session, unique_email)

    long_ago = datetime.now(timezone.utc) - timedelta(minutes=30)
    await db_session.execute(
        update(DeliveryJob)
        .where(DeliveryJob.id == job_id)
        .values(status=DeliveryJobStatus.PROCESSING.value, updated_at=long_ago)
    )
    await db_session.commit()

    fake_queue = InMemoryQueueClient()
    result = await reconcile_stuck_jobs(db_session, queue_client=fake_queue)

    assert result.recovered_stuck_processing == [job_id]
    assert job_id in fake_queue.queued

    job = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
    assert job.status == DeliveryJobStatus.RETRYING.value
    assert job.next_attempt_at is not None

    # And now it's actually recoverable via the normal claim path -- proves this
    # isn't just a status flip, the job is genuinely re-runnable.
    import httpx

    async def _ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_ok))
    from app.modules.delivery import executor as executor_module

    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    orig = executor_module.resolve_and_validate
    executor_module.resolve_and_validate = _fake_resolve
    try:
        job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    finally:
        executor_module.resolve_and_validate = orig
        await mock_client.aclose()

    assert job.status == DeliveryJobStatus.SUCCESS.value


@pytest.mark.asyncio
async def test_reconciliation_does_not_touch_recently_processing_job(client, unique_email, db_session):
    """A job that has been processing for a few seconds is not "stuck" -- it's just running."""
    job_id = await _publish_and_get_job_id(client, db_session, unique_email)
    recent = datetime.now(timezone.utc) - timedelta(seconds=5)
    await db_session.execute(
        update(DeliveryJob).where(DeliveryJob.id == job_id).values(status=DeliveryJobStatus.PROCESSING.value, updated_at=recent)
    )
    await db_session.commit()

    fake_queue = InMemoryQueueClient()
    result = await reconcile_stuck_jobs(db_session, queue_client=fake_queue)

    assert result.recovered_stuck_processing == []
    assert fake_queue.queued == []

    job = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
    assert job.status == DeliveryJobStatus.PROCESSING.value


@pytest.mark.asyncio
async def test_reconciliation_requeues_stale_queued_job(client, unique_email, db_session):
    """Simulates a job whose row was persisted but whose broker dispatch was lost."""
    job_id = await _publish_and_get_job_id(client, db_session, unique_email)
    stale = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db_session.execute(update(DeliveryJob).where(DeliveryJob.id == job_id).values(updated_at=stale))
    await db_session.commit()

    fake_queue = InMemoryQueueClient()
    result = await reconcile_stuck_jobs(db_session, queue_client=fake_queue)

    assert result.requeued_stale_queued == [job_id]
    assert job_id in fake_queue.queued

    job = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
    assert job.status == DeliveryJobStatus.QUEUED.value  # unchanged status, just re-dispatched


@pytest.mark.asyncio
async def test_reconciliation_requeues_missed_retry(client, unique_email, db_session):
    job_id = await _publish_and_get_job_id(client, db_session, unique_email)
    stale = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db_session.execute(
        update(DeliveryJob)
        .where(DeliveryJob.id == job_id)
        .values(status=DeliveryJobStatus.RETRYING.value, next_attempt_at=stale, updated_at=stale)
    )
    await db_session.commit()

    fake_queue = InMemoryQueueClient()
    result = await reconcile_stuck_jobs(db_session, queue_client=fake_queue)

    assert result.requeued_missed_retries == [job_id]
    assert job_id in fake_queue.queued


@pytest.mark.asyncio
async def test_reconciliation_is_idempotent_and_safe_to_run_concurrently(client, unique_email, db_session):
    """
    Running reconciliation twice in a row must not double-recover or double-requeue
    a job that the first pass already fixed.
    """
    job_id = await _publish_and_get_job_id(client, db_session, unique_email)
    long_ago = datetime.now(timezone.utc) - timedelta(minutes=30)
    await db_session.execute(
        update(DeliveryJob)
        .where(DeliveryJob.id == job_id)
        .values(status=DeliveryJobStatus.PROCESSING.value, updated_at=long_ago)
    )
    await db_session.commit()

    fake_queue = InMemoryQueueClient()
    first = await reconcile_stuck_jobs(db_session, queue_client=fake_queue)
    second = await reconcile_stuck_jobs(db_session, queue_client=fake_queue)

    assert first.recovered_stuck_processing == [job_id]
    assert second.recovered_stuck_processing == []  # already retrying now, not processing -- nothing to recover
    assert second.requeued_stale_queued == []
    assert second.requeued_missed_retries == []  # next_attempt_at was just set to "now", not stale yet


@pytest.mark.asyncio
async def test_claim_records_worker_lease(client, unique_email, db_session):
    """
    Regression test for the lease fields themselves: claiming a job via
    execute_delivery_job must record which worker claimed it and when, since
    reconcile_stuck_jobs' lease path depends entirely on this being populated.
    """
    import httpx

    from app.modules.delivery import executor as executor_module
    from app.modules.delivery.executor import execute_delivery_job

    job_id = await _publish_and_get_job_id(client, db_session, unique_email)

    async def _ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_ok))

    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    orig = executor_module.resolve_and_validate
    executor_module.resolve_and_validate = _fake_resolve
    try:
        before = datetime.now(timezone.utc)
        job = await execute_delivery_job(db_session, job_id=job_id, worker_id="host-x-99", http_client=mock_client)
    finally:
        executor_module.resolve_and_validate = orig
        await mock_client.aclose()

    assert job.claimed_by_worker_id == "host-x-99"
    assert job.claimed_at is not None
    claimed_at = job.claimed_at if job.claimed_at.tzinfo else job.claimed_at.replace(tzinfo=timezone.utc)
    assert claimed_at >= before


@pytest.mark.asyncio
async def test_reconciliation_lease_overrides_time_heuristic_when_worker_alive(client, unique_email, db_session):
    """
    The core value of the lease: a job stuck in `processing` for far longer than
    STUCK_PROCESSING_AFTER (10 min) must NOT be recovered if its claiming worker
    still has a fresh heartbeat -- the worker is doing something, even if slowly.
    Recovering it anyway would risk a duplicate concurrent delivery attempt, which
    is exactly what a real lease is supposed to prevent.
    """
    from app.modules.admin import service as admin_service

    job_id = await _publish_and_get_job_id(client, db_session, unique_email)

    now = datetime.now(timezone.utc)
    long_ago = now - timedelta(minutes=30)  # well past the 10-minute time heuristic
    await db_session.execute(
        update(DeliveryJob)
        .where(DeliveryJob.id == job_id)
        .values(
            status=DeliveryJobStatus.PROCESSING.value,
            updated_at=long_ago,
            claimed_by_worker_id="host-alive-1",
            claimed_at=long_ago,
        )
    )
    await db_session.commit()

    # worker is heartbeating right now -- clearly alive
    await admin_service.upsert_worker_heartbeat(db_session, worker_id="host-alive-1", hostname="host-alive", pid=1, now=now)

    fake_queue = InMemoryQueueClient()
    result = await reconcile_stuck_jobs(db_session, queue_client=fake_queue, now=now)

    assert result.recovered_stuck_processing == []
    assert result.recovered_via_lease == []
    assert result.recovered_via_time_heuristic == []
    assert fake_queue.queued == []

    job = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
    assert job.status == DeliveryJobStatus.PROCESSING.value


@pytest.mark.asyncio
async def test_reconciliation_lease_recovers_job_fast_when_worker_confirmed_dead(client, unique_email, db_session):
    """
    The other half of the lease's value: a job whose claiming worker's heartbeat
    has gone stale is recovered immediately -- well before the 10-minute time
    heuristic would have kicked in -- because the lease gives a much stronger,
    faster signal that the worker (and therefore the job) is genuinely abandoned.
    """
    from app.modules.admin import service as admin_service

    job_id = await _publish_and_get_job_id(client, db_session, unique_email)

    now = datetime.now(timezone.utc)
    recently_claimed = now - timedelta(minutes=2)  # nowhere near the 10-minute time heuristic
    await db_session.execute(
        update(DeliveryJob)
        .where(DeliveryJob.id == job_id)
        .values(
            status=DeliveryJobStatus.PROCESSING.value,
            updated_at=recently_claimed,
            claimed_by_worker_id="host-dead-1",
            claimed_at=recently_claimed,
        )
    )
    await db_session.commit()

    # this worker's last heartbeat was well past LEASE_WORKER_STALE_AFTER (90s) --
    # confirmed dead, even though only 2 minutes have passed overall
    stale_heartbeat = now - timedelta(minutes=2)
    await admin_service.upsert_worker_heartbeat(
        db_session, worker_id="host-dead-1", hostname="host-dead", pid=1, now=stale_heartbeat
    )

    fake_queue = InMemoryQueueClient()
    result = await reconcile_stuck_jobs(db_session, queue_client=fake_queue, now=now)

    assert result.recovered_via_lease == [job_id]
    assert result.recovered_via_time_heuristic == []
    assert job_id in fake_queue.queued

    job = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
    assert job.status == DeliveryJobStatus.RETRYING.value


@pytest.mark.asyncio
async def test_reconciliation_falls_back_to_time_heuristic_when_worker_has_no_heartbeat_history(
    client, unique_email, db_session
):
    """
    A job claimed by a worker_id with zero rows in worker_heartbeats (e.g. claimed
    before the heartbeat feature was deployed, or the worker's first heartbeat
    write never landed) has no usable lease signal -- reconciliation must fall back
    to the original time-only heuristic rather than treating "no data" as "alive".
    """
    job_id = await _publish_and_get_job_id(client, db_session, unique_email)

    now = datetime.now(timezone.utc)
    long_ago = now - timedelta(minutes=30)
    await db_session.execute(
        update(DeliveryJob)
        .where(DeliveryJob.id == job_id)
        .values(
            status=DeliveryJobStatus.PROCESSING.value,
            updated_at=long_ago,
            claimed_by_worker_id="host-unknown-1",  # no worker_heartbeats row for this worker_id at all
            claimed_at=long_ago,
        )
    )
    await db_session.commit()

    fake_queue = InMemoryQueueClient()
    result = await reconcile_stuck_jobs(db_session, queue_client=fake_queue, now=now)

    assert result.recovered_via_lease == []
    assert result.recovered_via_time_heuristic == [job_id]
    assert job_id in fake_queue.queued
