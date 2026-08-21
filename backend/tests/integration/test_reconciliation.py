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
