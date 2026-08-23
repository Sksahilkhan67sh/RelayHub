import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.modules.delivery import executor as executor_module
from app.modules.delivery.executor import execute_delivery_job
from app.modules.delivery.models import DeliveryJob
from tests.conftest import create_api_key, create_endpoint, register_and_get_token, upgrade_to_pro


@pytest.fixture(autouse=True)
def patch_connect_time_resolution(monkeypatch):
    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve)


def _ok_200(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200)


@pytest.mark.asyncio
async def test_search_by_status(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    success_resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "s1"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    failed_resp = await client.post(
        "/v1/events", json={"event": "payment.failed", "payload": {}, "idempotency_key": "f1"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    success_job_id = uuid.UUID(success_resp.json()["delivery_jobs"][0]["id"])
    failed_job_id = uuid.UUID(failed_resp.json()["delivery_jobs"][0]["id"])

    mock_ok = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    mock_fail = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    await execute_delivery_job(db_session, job_id=success_job_id, http_client=mock_ok)
    await execute_delivery_job(db_session, job_id=failed_job_id, http_client=mock_fail)
    await mock_ok.aclose()
    await mock_fail.aclose()

    success_search = await client.get("/v1/logs?status=success", headers={"Authorization": f"Bearer {token}"})
    assert len(success_search.json()) == 1
    assert success_search.json()[0]["id"] == str(success_job_id)

    failed_search = await client.get("/v1/logs?status=failed", headers={"Authorization": f"Bearer {token}"})
    assert len(failed_search.json()) == 1
    assert failed_search.json()[0]["id"] == str(failed_job_id)

    both_search = await client.get("/v1/logs?status=success&status=failed", headers={"Authorization": f"Bearer {token}"})
    assert len(both_search.json()) == 2


@pytest.mark.asyncio
async def test_pending_alias_expands_to_queued_and_processing(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    # never executed -- stays "queued"
    search_resp = await client.get("/v1/logs?status=pending", headers={"Authorization": f"Bearer {token}"})
    assert len(search_resp.json()) == 1
    assert search_resp.json()[0]["status"] == "queued"


@pytest.mark.asyncio
async def test_search_by_event_type_and_environment(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await upgrade_to_pro(client, db_session, token)
    await create_endpoint(client, token, environment="test")
    await create_endpoint(client, token, environment="live", url="https://live.example.com/hook")
    api_key_test = await create_api_key(client, token, environment="test")
    api_key_live = await create_api_key(client, token, environment="live")

    await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "environment": "test"},
        headers={"X-RelayHub-Api-Key": api_key_test},
    )
    await client.post(
        "/v1/events", json={"event": "order.created", "payload": {}, "environment": "live"},
        headers={"X-RelayHub-Api-Key": api_key_live},
    )

    by_type = await client.get("/v1/logs?event_type=payment.success", headers={"Authorization": f"Bearer {token}"})
    assert len(by_type.json()) == 1
    assert by_type.json()[0]["event_type"] == "payment.success"

    by_env = await client.get("/v1/logs?environment=live", headers={"Authorization": f"Bearer {token}"})
    assert len(by_env.json()) == 1
    assert by_env.json()[0]["environment"] == "live"


@pytest.mark.asyncio
async def test_search_by_request_id(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    publish_resp = await client.post(
        "/v1/events",
        json={"event": "payment.success", "payload": {}},
        headers={"X-RelayHub-Api-Key": api_key, "X-Request-ID": "trace-abc-123"},
    )
    job_id = publish_resp.json()["delivery_jobs"][0]["id"]

    search_resp = await client.get("/v1/logs?request_id=trace-abc-123", headers={"Authorization": f"Bearer {token}"})
    assert len(search_resp.json()) == 1
    assert search_resp.json()[0]["id"] == job_id
    assert search_resp.json()[0]["request_id"] == "trace-abc-123"


@pytest.mark.asyncio
async def test_search_by_endpoint_id(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await upgrade_to_pro(client, db_session, token)
    endpoint_a = await create_endpoint(client, token, url="https://a.example.com/hook", subscribed_event_types=["payment.success"])
    endpoint_b = await create_endpoint(client, token, url="https://b.example.com/hook", subscribed_event_types=["order.created"])
    api_key = await create_api_key(client, token)

    await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    await client.post(
        "/v1/events", json={"event": "order.created", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )

    resp = await client.get(f"/v1/logs?endpoint_id={endpoint_a}", headers={"Authorization": f"Bearer {token}"})
    assert len(resp.json()) == 1
    assert resp.json()[0]["endpoint_id"] == endpoint_a


@pytest.mark.asyncio
async def test_search_by_worker_id(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = uuid.UUID(resp.json()["delivery_jobs"][0]["id"])

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    await execute_delivery_job(db_session, job_id=job_id, worker_id="worker-xyz-1", http_client=mock_client)
    await mock_client.aclose()

    match = await client.get("/v1/logs?worker_id=worker-xyz-1", headers={"Authorization": f"Bearer {token}"})
    assert len(match.json()) == 1

    no_match = await client.get("/v1/logs?worker_id=nonexistent-worker", headers={"Authorization": f"Bearer {token}"})
    assert len(no_match.json()) == 0


@pytest.mark.asyncio
async def test_search_by_latency_range(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = uuid.UUID(resp.json()["delivery_jobs"][0]["id"])

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    wide_range = await client.get("/v1/logs?min_latency_ms=0&max_latency_ms=100000", headers={"Authorization": f"Bearer {token}"})
    assert len(wide_range.json()) == 1

    impossible_range = await client.get("/v1/logs?min_latency_ms=999999", headers={"Authorization": f"Bearer {token}"})
    assert len(impossible_range.json()) == 0


@pytest.mark.asyncio
async def test_search_by_date_range(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = resp.json()["delivery_jobs"][0]["id"]

    future_start = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    none_expected = await client.get(
        "/v1/logs", params={"queued_after": future_start}, headers={"Authorization": f"Bearer {token}"}
    )
    assert none_expected.status_code == 200, none_expected.text
    assert len(none_expected.json()) == 0

    past_start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    one_expected = await client.get(
        "/v1/logs", params={"queued_after": past_start}, headers={"Authorization": f"Bearer {token}"}
    )
    assert one_expected.status_code == 200, one_expected.text
    assert len(one_expected.json()) == 1
    assert one_expected.json()[0]["id"] == job_id


@pytest.mark.asyncio
async def test_pagination(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    for i in range(5):
        await client.post(
            "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": f"page-{i}"},
            headers={"X-RelayHub-Api-Key": api_key},
        )

    page1 = await client.get("/v1/logs?limit=2&offset=0", headers={"Authorization": f"Bearer {token}"})
    page2 = await client.get("/v1/logs?limit=2&offset=2", headers={"Authorization": f"Bearer {token}"})
    assert len(page1.json()) == 2
    assert len(page2.json()) == 2
    assert {j["id"] for j in page1.json()}.isdisjoint({j["id"] for j in page2.json()})


@pytest.mark.asyncio
async def test_retention_cleanup_deletes_only_expired_terminal_jobs(client, unique_email, db_session):
    from app.modules.auth.models import Organization
    from app.modules.logs.retention import cleanup_expired_delivery_logs

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    resp1 = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "old-success"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    old_job_id = uuid.UUID(resp1.json()["delivery_jobs"][0]["id"])

    resp2 = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "recent-success"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    recent_job_id = uuid.UUID(resp2.json()["delivery_jobs"][0]["id"])

    resp3 = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "old-queued"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    old_queued_job_id = uuid.UUID(resp3.json()["delivery_jobs"][0]["id"])

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    await execute_delivery_job(db_session, job_id=old_job_id, http_client=mock_client)
    await execute_delivery_job(db_session, job_id=recent_job_id, http_client=mock_client)
    await mock_client.aclose()

    org = (await db_session.execute(select(Organization))).scalars().first()
    org.log_retention_days = 7
    old_job = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == old_job_id))).scalar_one()
    old_job.completed_at = datetime.now(timezone.utc) - timedelta(days=10)
    old_queued_job = (
        await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == old_queued_job_id))
    ).scalar_one()
    old_queued_job.queued_at = datetime.now(timezone.utc) - timedelta(days=10)
    await db_session.commit()

    deleted_count = await cleanup_expired_delivery_logs(db_session)
    assert deleted_count == 1

    remaining_ids = {str(j.id) for j in (await db_session.execute(select(DeliveryJob))).scalars().all()}
    assert str(old_job_id) not in remaining_ids
    assert str(recent_job_id) in remaining_ids
    assert str(old_queued_job_id) in remaining_ids  # never touched -- still in flight
