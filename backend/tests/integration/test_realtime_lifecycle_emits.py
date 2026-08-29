"""
Verifies the DLQ-replay and reconciliation state-transition points each publish
the realtime `delivery.updated` event they're supposed to (spec Steps 11/12 --
retry/DLQ events -- plus the reconciliation "retrying" recovery path), strictly
after their own DB commit, without duplicating anything test_dlq.py /
test_reconciliation.py already cover about the underlying transition itself.
"""

import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import update

from app.common.queue_client import InMemoryQueueClient
from app.modules.delivery import executor as executor_module
from app.modules.delivery.executor import execute_delivery_job
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus
from app.modules.retry.reconciliation import reconcile_stuck_jobs
from tests.conftest import create_api_key, create_endpoint, register_and_get_token, upgrade_to_pro


@pytest.fixture(autouse=True)
def patch_connect_time_resolution(monkeypatch):
    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve)


def _always_503(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503, text="down")


async def _create_dead_lettered_job(client, token, db_session) -> uuid.UUID:
    endpoint_id = await create_endpoint(client, token, url=f"https://example.com/hook/{uuid.uuid4().hex[:8]}")
    await client.patch(
        f"/v1/endpoints/{endpoint_id}", json={"max_retry_attempts": 0}, headers={"Authorization": f"Bearer {token}"}
    )
    api_key = await create_api_key(client, token)
    resp = await client.post(
        "/v1/events",
        json={"event": "payment.success", "payload": {"amount": 1}, "idempotency_key": str(uuid.uuid4())},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    job_id = uuid.UUID(resp.json()["delivery_jobs"][0]["id"])

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_always_503))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client, realtime_publisher=client.fake_realtime)
    await mock_client.aclose()
    assert job.status == "dead_letter"
    client.fake_realtime.published.clear()  # isolate assertions to the retry action itself
    return job_id


@pytest.mark.asyncio
async def test_dlq_single_retry_emits_queued_event(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    job_id = await _create_dead_lettered_job(client, token, db_session)

    resp = await client.post(f"/v1/dlq/{job_id}/retry", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    assert len(client.fake_realtime.published) == 1
    _org_id, payload = client.fake_realtime.published[0]
    assert payload["delivery_job_id"] == str(job_id)
    assert payload["status"] == "queued"
    assert payload["attempt_number"] == 0


@pytest.mark.asyncio
async def test_dlq_bulk_retry_emits_one_queued_event_per_job(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await upgrade_to_pro(client, db_session, token)
    job_id_a = await _create_dead_lettered_job(client, token, db_session)
    job_id_b = await _create_dead_lettered_job(client, token, db_session)

    resp = await client.post(
        "/v1/dlq/bulk-retry",
        json={"job_ids": [str(job_id_a), str(job_id_b)]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert set(resp.json()["retried"]) == {str(job_id_a), str(job_id_b)}

    statuses_by_job = {p["delivery_job_id"]: p["status"] for _org, p in client.fake_realtime.published}
    assert statuses_by_job == {str(job_id_a): "queued", str(job_id_b): "queued"}


@pytest.mark.asyncio
async def test_reconciliation_emits_retrying_event_for_recovered_stuck_job(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    publish_resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = uuid.UUID(publish_resp.json()["delivery_jobs"][0]["id"])

    long_ago = datetime.now(timezone.utc) - timedelta(minutes=30)
    await db_session.execute(
        update(DeliveryJob)
        .where(DeliveryJob.id == job_id)
        .values(status=DeliveryJobStatus.PROCESSING.value, updated_at=long_ago)
    )
    await db_session.commit()
    client.fake_realtime.published.clear()

    fake_queue = InMemoryQueueClient()
    result = await reconcile_stuck_jobs(db_session, queue_client=fake_queue, realtime_publisher=client.fake_realtime)
    assert result.recovered_stuck_processing == [job_id]

    assert len(client.fake_realtime.published) == 1
    _org_id, payload = client.fake_realtime.published[0]
    assert payload["delivery_job_id"] == str(job_id)
    assert payload["status"] == "retrying"
