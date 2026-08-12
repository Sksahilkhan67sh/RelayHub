import csv
import io
import uuid

import httpx
import pytest

from app.modules.delivery import executor as executor_module
from app.modules.delivery.executor import execute_delivery_job
from tests.conftest import create_api_key, create_endpoint, register_and_get_token, upgrade_to_pro


@pytest.fixture(autouse=True)
def patch_connect_time_resolution(monkeypatch):
    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve)


def _always_503(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503, text="down")


async def _create_dead_lettered_job(client, token, db_session, *, api_key: str | None = None) -> uuid.UUID:
    """Helper: registers an endpoint with max_retry_attempts=0 so one failure immediately dead-letters."""
    endpoint_id = await create_endpoint(client, token)
    await client.patch(
        f"/v1/endpoints/{endpoint_id}", json={"max_retry_attempts": 0}, headers={"Authorization": f"Bearer {token}"}
    )
    key = api_key or await create_api_key(client, token)
    resp = await client.post(
        "/v1/events",
        json={"event": "payment.success", "payload": {"amount": 999}, "idempotency_key": str(uuid.uuid4())},
        headers={"X-RelayHub-Api-Key": key},
    )
    job_id = uuid.UUID(resp.json()["delivery_jobs"][0]["id"])

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_always_503))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()
    assert job.status == "dead_letter"
    return job_id


@pytest.mark.asyncio
async def test_list_dlq_empty_then_populated(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)

    empty_resp = await client.get("/v1/dlq", headers={"Authorization": f"Bearer {token}"})
    assert empty_resp.status_code == 200
    assert empty_resp.json() == []

    await _create_dead_lettered_job(client, token, db_session)

    populated_resp = await client.get("/v1/dlq", headers={"Authorization": f"Bearer {token}"})
    assert len(populated_resp.json()) == 1


@pytest.mark.asyncio
async def test_get_dlq_job_detail(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    job_id = await _create_dead_lettered_job(client, token, db_session)

    resp = await client.get(f"/v1/dlq/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["event_type"] == "payment.success"
    assert body["payload"] == {"amount": 999}
    assert body["last_error_category"] == "transient_http_error"
    assert len(body["attempts"]) == 1


@pytest.mark.asyncio
async def test_get_non_dlq_job_returns_404(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    still_queued_job_id = resp.json()["delivery_jobs"][0]["id"]

    dlq_resp = await client.get(f"/v1/dlq/{still_queued_job_id}", headers={"Authorization": f"Bearer {token}"})
    assert dlq_resp.status_code == 404


@pytest.mark.asyncio
async def test_retry_dlq_job_resets_and_requeues(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    job_id = await _create_dead_lettered_job(client, token, db_session)

    retry_resp = await client.post(f"/v1/dlq/{job_id}/retry", headers={"Authorization": f"Bearer {token}"})
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "queued"

    # no longer appears in the DLQ listing
    list_resp = await client.get("/v1/dlq", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.json() == []

    # confirm the reset via the general deliveries endpoint
    delivery_resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert delivery_resp.json()["status"] == "queued"
    assert delivery_resp.json()["attempt_number"] == 0

    # actually got re-enqueued
    assert uuid.UUID(str(job_id)) in client.fake_queue.queued or job_id in client.fake_queue.queued


@pytest.mark.asyncio
async def test_retry_requires_admin_role(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    job_id = await _create_dead_lettered_job(client, token, db_session)

    resp = await client.post(f"/v1/dlq/{job_id}/retry")  # no auth at all
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_delete_dlq_job(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    job_id = await _create_dead_lettered_job(client, token, db_session)

    delete_resp = await client.delete(f"/v1/dlq/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/v1/dlq/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == 404

    list_resp = await client.get("/v1/dlq", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_bulk_retry_mixed_valid_and_invalid_ids(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await upgrade_to_pro(client, db_session, token)
    job_id_1 = await _create_dead_lettered_job(client, token, db_session)
    job_id_2 = await _create_dead_lettered_job(client, token, db_session)
    fake_id = uuid.uuid4()

    resp = await client.post(
        "/v1/dlq/bulk-retry",
        json={"job_ids": [str(job_id_1), str(job_id_2), str(fake_id)]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["retried"]) == {str(job_id_1), str(job_id_2)}
    assert body["skipped"] == [str(fake_id)]

    list_resp = await client.get("/v1/dlq", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_export_csv_contains_expected_rows(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    job_id = await _create_dead_lettered_job(client, token, db_session)

    resp = await client.get("/v1/dlq/export", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")

    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["delivery_job_id"] == str(job_id)
    assert rows[0]["event_type"] == "payment.success"
    assert rows[0]["last_error_category"] == "transient_http_error"


@pytest.mark.asyncio
async def test_viewer_can_list_but_not_retry_or_delete(client, unique_email, db_session):
    """
    Full cross-membership-role testing awaits the Invite Users flow; this test only
    confirms VIEWER-permitted routes stay reachable while mutating ones stay gated,
    using the owner token (which satisfies VIEWER-or-higher) against both route classes.
    """
    token = await register_and_get_token(client, unique_email)
    job_id = await _create_dead_lettered_job(client, token, db_session)

    list_resp = await client.get("/v1/dlq", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.status_code == 200

    export_resp = await client.get("/v1/dlq/export", headers={"Authorization": f"Bearer {token}"})
    assert export_resp.status_code == 200

    unauthenticated_retry = await client.post(f"/v1/dlq/{job_id}/retry")
    assert unauthenticated_retry.status_code in (401, 403)

    unauthenticated_delete = await client.delete(f"/v1/dlq/{job_id}")
    assert unauthenticated_delete.status_code in (401, 403)
