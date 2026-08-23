import uuid

import httpx
import pytest

from app.modules.delivery import executor as executor_module
from app.modules.delivery.executor import execute_delivery_job
from tests.conftest import create_api_key, create_endpoint, register_and_get_token


@pytest.fixture(autouse=True)
def patch_connect_time_resolution(monkeypatch):
    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve)


def _ok_200(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200)


def _not_found_404(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_summary_reflects_deliveries_and_events(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    ok_resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "ok1"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    fail_resp = await client.post(
        "/v1/events", json={"event": "payment.failed", "payload": {}, "idempotency_key": "f1"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    ok_job_id = uuid.UUID(ok_resp.json()["delivery_jobs"][0]["id"])
    fail_job_id = uuid.UUID(fail_resp.json()["delivery_jobs"][0]["id"])

    mock_ok = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    mock_fail = httpx.AsyncClient(transport=httpx.MockTransport(_not_found_404))
    await execute_delivery_job(db_session, job_id=ok_job_id, http_client=mock_ok)
    await execute_delivery_job(db_session, job_id=fail_job_id, http_client=mock_fail)
    await mock_ok.aclose()
    await mock_fail.aclose()

    resp = await client.get("/v1/analytics/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_events"] == 2
    assert body["total_deliveries"] == 2
    assert body["success_count"] == 1
    assert body["failed_count"] == 1
    assert body["success_rate"] == 0.5
    assert body["failure_rate"] == 0.5
    assert body["latency_p50_ms"] is not None


@pytest.mark.asyncio
async def test_summary_with_no_data_returns_none_rates_not_error(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.get("/v1/analytics/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_deliveries"] == 0
    assert body["success_rate"] is None
    assert body["latency_p50_ms"] is None


@pytest.mark.asyncio
async def test_summary_environment_scoping(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token, environment="live")
    live_key = await create_api_key(client, token, environment="live")

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "environment": "live"},
        headers={"X-RelayHub-Api-Key": live_key},
    )
    job_id = uuid.UUID(resp.json()["delivery_jobs"][0]["id"])
    mock_ok = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    await execute_delivery_job(db_session, job_id=job_id, http_client=mock_ok)
    await mock_ok.aclose()

    live_summary = await client.get("/v1/analytics/summary?environment=live", headers={"Authorization": f"Bearer {token}"})
    assert live_summary.json()["total_deliveries"] == 1

    test_summary = await client.get("/v1/analytics/summary?environment=test", headers={"Authorization": f"Bearer {token}"})
    assert test_summary.json()["total_deliveries"] == 0


@pytest.mark.asyncio
async def test_deliveries_over_time_buckets_by_hour(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = uuid.UUID(resp.json()["delivery_jobs"][0]["id"])
    mock_ok = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    await execute_delivery_job(db_session, job_id=job_id, http_client=mock_ok)
    await mock_ok.aclose()

    ts_resp = await client.get("/v1/analytics/deliveries-over-time?granularity=hour", headers={"Authorization": f"Bearer {token}"})
    assert ts_resp.status_code == 200
    buckets = ts_resp.json()
    assert len(buckets) == 1
    assert buckets[0]["total_count"] == 1
    assert buckets[0]["success_count"] == 1


@pytest.mark.asyncio
async def test_events_by_type_counts_correctly(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    for i in range(3):
        await client.post(
            "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": f"s{i}"},
            headers={"X-RelayHub-Api-Key": api_key},
        )
    await client.post(
        "/v1/events", json={"event": "order.created", "payload": {}, "idempotency_key": "o1"},
        headers={"X-RelayHub-Api-Key": api_key},
    )

    resp = await client.get("/v1/analytics/events-by-type", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    by_type = {row["event_type"]: row["count"] for row in resp.json()}
    assert by_type["payment.success"] == 3
    assert by_type["order.created"] == 1


@pytest.mark.asyncio
async def test_top_endpoints_ranks_by_delivery_count_and_computes_correct_success_rate(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    # 2 successes, 1 permanent failure -> success_rate should be 2/3, NOT inflated by
    # multiple attempts per job (regression test for the join-multiplication bug)
    ids = []
    for i in range(3):
        resp = await client.post(
            "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": f"job{i}"},
            headers={"X-RelayHub-Api-Key": api_key},
        )
        ids.append(uuid.UUID(resp.json()["delivery_jobs"][0]["id"]))

    mock_ok = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    mock_fail = httpx.AsyncClient(transport=httpx.MockTransport(_not_found_404))
    await execute_delivery_job(db_session, job_id=ids[0], http_client=mock_ok)
    await execute_delivery_job(db_session, job_id=ids[1], http_client=mock_ok)
    await execute_delivery_job(db_session, job_id=ids[2], http_client=mock_fail)
    await mock_ok.aclose()
    await mock_fail.aclose()

    resp = await client.get("/v1/analytics/top-endpoints", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["endpoint_id"] == endpoint_id
    assert row["delivery_count"] == 3
    assert row["success_count"] == 2
    assert abs(row["success_rate"] - (2 / 3)) < 1e-9
    assert row["avg_latency_ms"] is not None


@pytest.mark.asyncio
async def test_endpoint_health_reflects_circuit_breaker_state(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.endpoints import service as endpoint_service
    from app.modules.endpoints.models import Endpoint

    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)

    endpoint = (await db_session.execute(select(Endpoint).where(Endpoint.id == uuid.UUID(endpoint_id)))).scalar_one()
    for _ in range(10):
        endpoint = await endpoint_service.record_delivery_result(db_session, endpoint=endpoint, success=False)

    resp = await client.get("/v1/analytics/endpoint-health", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["health_status"] == "unhealthy"
    assert rows[0]["is_active"] is False
    assert rows[0]["consecutive_failure_count"] == 10


@pytest.mark.asyncio
async def test_analytics_requires_auth(client):
    resp = await client.get("/v1/analytics/summary")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_export_csv_for_deliveries_over_time(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = uuid.UUID(resp.json()["delivery_jobs"][0]["id"])
    mock_ok = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    await execute_delivery_job(db_session, job_id=job_id, http_client=mock_ok)
    await mock_ok.aclose()

    export_resp = await client.get(
        "/v1/analytics/export?report=deliveries-over-time", headers={"Authorization": f"Bearer {token}"}
    )
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"].startswith("text/csv")
    assert "bucket,total_count,success_count,failed_count" in export_resp.text


@pytest.mark.asyncio
async def test_export_csv_for_top_endpoints(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)

    resp = await client.get(
        "/v1/analytics/export?report=top-endpoints", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert "endpoint_id,name,delivery_count" in resp.text


@pytest.mark.asyncio
async def test_insights_alias_mirrors_analytics_for_ad_blocker_avoidance(client, unique_email):
    """
    Regression test: /v1/insights/* must be a true alias of /v1/analytics/*, not a
    separate implementation, so the two can never silently drift apart. Added
    because ad-blocker/privacy-extension filter lists commonly match the substring
    "analytics" in first-party request URLs (net::ERR_BLOCKED_BY_CLIENT), which was
    breaking the dashboard's own analytics page for some users -- the first-party
    web app now calls /v1/insights/* instead, while /v1/analytics/* stays exactly
    as published for the SDKs and API docs.
    """
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)

    for path in ("summary", "events-by-type", "endpoint-health"):
        analytics_resp = await client.get(f"/v1/analytics/{path}", headers={"Authorization": f"Bearer {token}"})
        insights_resp = await client.get(f"/v1/insights/{path}", headers={"Authorization": f"Bearer {token}"})
        assert analytics_resp.status_code == insights_resp.status_code == 200
        assert analytics_resp.json() == insights_resp.json()


@pytest.mark.asyncio
async def test_insights_path_excluded_from_openapi_schema(client):
    """
    /v1/insights/{summary,deliveries-over-time,events-by-type,top-endpoints,
    endpoint-health,export} is the internal analytics alias -- not a second public
    API surface to document, so those specific paths must not appear twice.

    NOTE (Phase 3): /v1/insights/intelligence/* is NOT part of that alias -- it's
    a separate, genuinely new, intentionally-documented API (see
    app/modules/insights/routes.py). This assertion was originally a blanket
    "nothing under /v1/insights/" check; narrowed to the specific alias paths so
    it still catches the alias being accidentally re-documented without also
    asserting the new intelligence endpoints must be hidden from API consumers.
    """
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert any(p.startswith("/v1/analytics/") for p in paths)

    aliased_paths = {"/summary", "/deliveries-over-time", "/events-by-type", "/top-endpoints", "/endpoint-health", "/export"}
    for suffix in aliased_paths:
        assert f"/v1/insights{suffix}" not in paths

    # The Phase 3 intelligence API, by contrast, IS expected to be documented.
    assert any(p.startswith("/v1/insights/intelligence") for p in paths)
import uuid

import httpx
import pytest

from app.modules.delivery import executor as executor_module
from app.modules.delivery.executor import execute_delivery_job
from tests.conftest import create_api_key, create_endpoint, register_and_get_token


@pytest.fixture(autouse=True)
def patch_connect_time_resolution(monkeypatch):
    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve)


def _ok_200(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200)


def _not_found_404(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_summary_reflects_deliveries_and_events(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    ok_resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "ok1"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    fail_resp = await client.post(
        "/v1/events", json={"event": "payment.failed", "payload": {}, "idempotency_key": "f1"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    ok_job_id = uuid.UUID(ok_resp.json()["delivery_jobs"][0]["id"])
    fail_job_id = uuid.UUID(fail_resp.json()["delivery_jobs"][0]["id"])

    mock_ok = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    mock_fail = httpx.AsyncClient(transport=httpx.MockTransport(_not_found_404))
    await execute_delivery_job(db_session, job_id=ok_job_id, http_client=mock_ok)
    await execute_delivery_job(db_session, job_id=fail_job_id, http_client=mock_fail)
    await mock_ok.aclose()
    await mock_fail.aclose()

    resp = await client.get("/v1/analytics/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_events"] == 2
    assert body["total_deliveries"] == 2
    assert body["success_count"] == 1
    assert body["failed_count"] == 1
    assert body["success_rate"] == 0.5
    assert body["failure_rate"] == 0.5
    assert body["latency_p50_ms"] is not None


@pytest.mark.asyncio
async def test_summary_with_no_data_returns_none_rates_not_error(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.get("/v1/analytics/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_deliveries"] == 0
    assert body["success_rate"] is None
    assert body["latency_p50_ms"] is None


@pytest.mark.asyncio
async def test_summary_environment_scoping(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token, environment="live")
    live_key = await create_api_key(client, token, environment="live")

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "environment": "live"},
        headers={"X-RelayHub-Api-Key": live_key},
    )
    job_id = uuid.UUID(resp.json()["delivery_jobs"][0]["id"])
    mock_ok = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    await execute_delivery_job(db_session, job_id=job_id, http_client=mock_ok)
    await mock_ok.aclose()

    live_summary = await client.get("/v1/analytics/summary?environment=live", headers={"Authorization": f"Bearer {token}"})
    assert live_summary.json()["total_deliveries"] == 1

    test_summary = await client.get("/v1/analytics/summary?environment=test", headers={"Authorization": f"Bearer {token}"})
    assert test_summary.json()["total_deliveries"] == 0


@pytest.mark.asyncio
async def test_deliveries_over_time_buckets_by_hour(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = uuid.UUID(resp.json()["delivery_jobs"][0]["id"])
    mock_ok = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    await execute_delivery_job(db_session, job_id=job_id, http_client=mock_ok)
    await mock_ok.aclose()

    ts_resp = await client.get("/v1/analytics/deliveries-over-time?granularity=hour", headers={"Authorization": f"Bearer {token}"})
    assert ts_resp.status_code == 200
    buckets = ts_resp.json()
    assert len(buckets) == 1
    assert buckets[0]["total_count"] == 1
    assert buckets[0]["success_count"] == 1


@pytest.mark.asyncio
async def test_events_by_type_counts_correctly(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    for i in range(3):
        await client.post(
            "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": f"s{i}"},
            headers={"X-RelayHub-Api-Key": api_key},
        )
    await client.post(
        "/v1/events", json={"event": "order.created", "payload": {}, "idempotency_key": "o1"},
        headers={"X-RelayHub-Api-Key": api_key},
    )

    resp = await client.get("/v1/analytics/events-by-type", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    by_type = {row["event_type"]: row["count"] for row in resp.json()}
    assert by_type["payment.success"] == 3
    assert by_type["order.created"] == 1


@pytest.mark.asyncio
async def test_top_endpoints_ranks_by_delivery_count_and_computes_correct_success_rate(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    # 2 successes, 1 permanent failure -> success_rate should be 2/3, NOT inflated by
    # multiple attempts per job (regression test for the join-multiplication bug)
    ids = []
    for i in range(3):
        resp = await client.post(
            "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": f"job{i}"},
            headers={"X-RelayHub-Api-Key": api_key},
        )
        ids.append(uuid.UUID(resp.json()["delivery_jobs"][0]["id"]))

    mock_ok = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    mock_fail = httpx.AsyncClient(transport=httpx.MockTransport(_not_found_404))
    await execute_delivery_job(db_session, job_id=ids[0], http_client=mock_ok)
    await execute_delivery_job(db_session, job_id=ids[1], http_client=mock_ok)
    await execute_delivery_job(db_session, job_id=ids[2], http_client=mock_fail)
    await mock_ok.aclose()
    await mock_fail.aclose()

    resp = await client.get("/v1/analytics/top-endpoints", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["endpoint_id"] == endpoint_id
    assert row["delivery_count"] == 3
    assert row["success_count"] == 2
    assert abs(row["success_rate"] - (2 / 3)) < 1e-9
    assert row["avg_latency_ms"] is not None


@pytest.mark.asyncio
async def test_endpoint_health_reflects_circuit_breaker_state(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.endpoints import service as endpoint_service
    from app.modules.endpoints.models import Endpoint

    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)

    endpoint = (await db_session.execute(select(Endpoint).where(Endpoint.id == uuid.UUID(endpoint_id)))).scalar_one()
    for _ in range(10):
        endpoint = await endpoint_service.record_delivery_result(db_session, endpoint=endpoint, success=False)

    resp = await client.get("/v1/analytics/endpoint-health", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["health_status"] == "unhealthy"
    assert rows[0]["is_active"] is False
    assert rows[0]["consecutive_failure_count"] == 10


@pytest.mark.asyncio
async def test_analytics_requires_auth(client):
    resp = await client.get("/v1/analytics/summary")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_export_csv_for_deliveries_over_time(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = uuid.UUID(resp.json()["delivery_jobs"][0]["id"])
    mock_ok = httpx.AsyncClient(transport=httpx.MockTransport(_ok_200))
    await execute_delivery_job(db_session, job_id=job_id, http_client=mock_ok)
    await mock_ok.aclose()

    export_resp = await client.get(
        "/v1/analytics/export?report=deliveries-over-time", headers={"Authorization": f"Bearer {token}"}
    )
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"].startswith("text/csv")
    assert "bucket,total_count,success_count,failed_count" in export_resp.text


@pytest.mark.asyncio
async def test_export_csv_for_top_endpoints(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)

    resp = await client.get(
        "/v1/analytics/export?report=top-endpoints", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert "endpoint_id,name,delivery_count" in resp.text


@pytest.mark.asyncio
async def test_insights_alias_mirrors_analytics_for_ad_blocker_avoidance(client, unique_email):
    """
    Regression test: /v1/insights/* must be a true alias of /v1/analytics/*, not a
    separate implementation, so the two can never silently drift apart. Added
    because ad-blocker/privacy-extension filter lists commonly match the substring
    "analytics" in first-party request URLs (net::ERR_BLOCKED_BY_CLIENT), which was
    breaking the dashboard's own analytics page for some users -- the first-party
    web app now calls /v1/insights/* instead, while /v1/analytics/* stays exactly
    as published for the SDKs and API docs.
    """
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)

    for path in ("summary", "events-by-type", "endpoint-health"):
        analytics_resp = await client.get(f"/v1/analytics/{path}", headers={"Authorization": f"Bearer {token}"})
        insights_resp = await client.get(f"/v1/insights/{path}", headers={"Authorization": f"Bearer {token}"})
        assert analytics_resp.status_code == insights_resp.status_code == 200
        assert analytics_resp.json() == insights_resp.json()


@pytest.mark.asyncio
async def test_insights_path_excluded_from_openapi_schema(client):
    """
    /v1/insights/{summary,deliveries-over-time,events-by-type,top-endpoints,
    endpoint-health,export} is the internal analytics alias -- not a second public
    API surface to document, so those specific paths must not appear twice.

    NOTE (Phase 3): /v1/insights/intelligence/* is NOT part of that alias -- it's
    a separate, genuinely new, intentionally-documented API (see
    app/modules/insights/routes.py). This assertion was originally a blanket
    "nothing under /v1/insights/" check; narrowed to the specific alias paths so
    it still catches the alias being accidentally re-documented without also
    asserting the new intelligence endpoints must be hidden from API consumers.
    """
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert any(p.startswith("/v1/analytics/") for p in paths)

    aliased_paths = {"/summary", "/deliveries-over-time", "/events-by-type", "/top-endpoints", "/endpoint-health", "/export"}
    for suffix in aliased_paths:
        assert f"/v1/insights{suffix}" not in paths

    # The Phase 3 intelligence API, by contrast, IS expected to be documented.
    assert any(p.startswith("/v1/insights/intelligence") for p in paths)
