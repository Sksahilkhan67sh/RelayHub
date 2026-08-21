import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.modules.delivery import executor as executor_module
from app.modules.delivery.executor import execute_delivery_job
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus
from app.modules.retry.scheduler import enqueue_due_retries
from tests.conftest import create_api_key, create_endpoint, register_and_get_token


@pytest.fixture(autouse=True)
def patch_connect_time_resolution(monkeypatch):
    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve)


def _always_503(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503, text="down")


@pytest.mark.asyncio
async def test_retrying_job_gets_increasing_next_attempt_at(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    publish_resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = uuid.UUID(publish_resp.json()["delivery_jobs"][0]["id"])

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_always_503))

    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    assert job.status == DeliveryJobStatus.RETRYING.value
    assert job.attempt_number == 1
    first_next_attempt = job.next_attempt_at
    assert first_next_attempt is not None

    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    assert job.status == DeliveryJobStatus.RETRYING.value
    assert job.attempt_number == 2
    second_next_attempt = job.next_attempt_at
    assert second_next_attempt > first_next_attempt, "Second retry delay (~30s) should schedule further out than the first (~10s)"

    await mock_client.aclose()


@pytest.mark.asyncio
async def test_job_moves_to_dead_letter_after_exhausting_endpoint_override_attempts(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)
    # override to a tiny attempt budget so the test doesn't need 8 iterations
    await client.patch(
        f"/v1/endpoints/{endpoint_id}", json={"max_retry_attempts": 2}, headers={"Authorization": f"Bearer {token}"}
    )
    api_key = await create_api_key(client, token)

    publish_resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = uuid.UUID(publish_resp.json()["delivery_jobs"][0]["id"])

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_always_503))

    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    assert job.status == DeliveryJobStatus.RETRYING.value  # attempt 1 of 2, one more allowed

    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    assert job.status == DeliveryJobStatus.DEAD_LETTER.value  # attempt 2 of 2, exhausted
    assert job.next_attempt_at is None

    await mock_client.aclose()


@pytest.mark.asyncio
async def test_zero_max_retry_attempts_dead_letters_on_first_failure(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)
    await client.patch(
        f"/v1/endpoints/{endpoint_id}", json={"max_retry_attempts": 0}, headers={"Authorization": f"Bearer {token}"}
    )
    api_key = await create_api_key(client, token)

    publish_resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = uuid.UUID(publish_resp.json()["delivery_jobs"][0]["id"])

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_always_503))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert job.status == DeliveryJobStatus.DEAD_LETTER.value


@pytest.mark.asyncio
async def test_scanner_enqueues_only_due_jobs(client, unique_email, db_session):
    from app.common.queue_client import InMemoryQueueClient

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    # create two delivery jobs by publishing two events
    resp1 = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "job-a"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    resp2 = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "job-b"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    job_a_id = uuid.UUID(resp1.json()["delivery_jobs"][0]["id"])
    job_b_id = uuid.UUID(resp2.json()["delivery_jobs"][0]["id"])

    now = datetime.now(timezone.utc)

    job_a = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_a_id))).scalar_one()
    job_a.status = DeliveryJobStatus.RETRYING.value
    job_a.next_attempt_at = now - timedelta(seconds=5)  # due

    job_b = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_b_id))).scalar_one()
    job_b.status = DeliveryJobStatus.RETRYING.value
    job_b.next_attempt_at = now + timedelta(minutes=10)  # not due yet

    await db_session.commit()

    fake_queue = InMemoryQueueClient()
    due_ids = await enqueue_due_retries(db_session, queue_client=fake_queue, now=now)

    assert due_ids == [job_a_id]
    assert fake_queue.queued == [job_a_id]

    # scanning does not change job status -- claim logic in the executor owns that
    await db_session.refresh(job_a)
    assert job_a.status == DeliveryJobStatus.RETRYING.value


@pytest.mark.asyncio
async def test_enqueue_due_retries_survives_one_broker_failure(client, unique_email, db_session):
    """
    Regression test: previously a single failed enqueue() call (e.g. broker
    temporarily unreachable) would raise out of enqueue_due_retries entirely,
    silently skipping every other due job in that scan. One failure must not take
    down the rest of the tick.
    """
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    resp_a = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "a"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    resp_b = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "b"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    job_a_id = uuid.UUID(resp_a.json()["delivery_jobs"][0]["id"])
    job_b_id = uuid.UUID(resp_b.json()["delivery_jobs"][0]["id"])

    now = datetime.now(timezone.utc)
    for job_id in (job_a_id, job_b_id):
        job = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
        job.status = DeliveryJobStatus.RETRYING.value
        job.next_attempt_at = now - timedelta(seconds=5)
    await db_session.commit()

    class FlakyQueueClient:
        def __init__(self):
            self.queued = []

        async def enqueue(self, job_id):
            if job_id == job_a_id:
                raise ConnectionError("simulated broker outage")
            self.queued.append(job_id)

    flaky_queue = FlakyQueueClient()
    due_ids = await enqueue_due_retries(db_session, queue_client=flaky_queue, now=now)

    assert set(due_ids) == {job_a_id, job_b_id}  # both were found as due
    assert flaky_queue.queued == [job_b_id]  # job_b still got dispatched despite job_a's failure
