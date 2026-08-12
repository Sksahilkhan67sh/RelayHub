import uuid

import httpx
import pytest
from sqlalchemy import select

from app.modules.delivery import executor as executor_module
from app.modules.delivery.executor import JobAlreadyClaimedError, execute_delivery_job
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus, ErrorCategory
from app.modules.endpoints.models import Endpoint, EndpointHealth, EndpointSecret
from tests.conftest import create_api_key, create_endpoint, register_and_get_token


async def _publish_and_get_job_id(client, token, api_key) -> uuid.UUID:
    resp = await client.post(
        "/v1/events",
        json={"event": "payment.success", "payload": {"amount": 4200}},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    assert resp.status_code == 201, resp.text
    job_id = resp.json()["delivery_jobs"][0]["id"]
    return uuid.UUID(job_id)


@pytest.fixture(autouse=True)
def patch_connect_time_resolution(monkeypatch):
    """
    Every test in this file exercises delivery logic, not DNS -- stub the connect-time
    SSRF re-check to return a fixed, non-blocked "resolved" IP unless a test
    specifically overrides it (see test_ssrf_block_at_delivery_time).
    """

    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve)


@pytest.mark.asyncio
async def test_successful_delivery_marks_job_success_and_records_attempt(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, token, api_key)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "X-Relayhub-Signature" in request.headers or "X-RelayHub-Signature" in {k: v for k, v in request.headers.items()}
        return httpx.Response(200, json={"received": True})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert job.status == DeliveryJobStatus.SUCCESS.value
    assert job.attempt_number == 1
    assert len(job.attempts) == 1
    attempt = job.attempts[0]
    assert attempt.http_status == 200
    assert attempt.error_category == ErrorCategory.NONE.value
    assert attempt.destination_ip == "93.184.216.34"
    assert attempt.duration_ms >= 0

    endpoint = (await db_session.execute(select(Endpoint).where(Endpoint.id == job.endpoint_id))).scalar_one()
    assert endpoint.health_status == EndpointHealth.HEALTHY.value
    assert endpoint.last_success_at is not None


@pytest.mark.asyncio
async def test_signature_headers_are_actually_valid(client, unique_email, db_session):
    """Round-trip check: the signature the worker sends must verify with the endpoint's real secret."""
    from app.core.encryption import decrypt_secret
    from app.modules.delivery.signing import verify

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, token, api_key)

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content
        return httpx.Response(200)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    job_row = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job.id))).scalar_one()
    endpoint = (await db_session.execute(select(Endpoint).where(Endpoint.id == job_row.endpoint_id))).scalar_one()
    secret_row = (
        await db_session.execute(
            select(EndpointSecret).where(EndpointSecret.endpoint_id == endpoint.id, EndpointSecret.is_primary.is_(True))
        )
    ).scalar_one()
    real_secret = decrypt_secret(secret_row.encrypted_secret)

    verify(
        secret=real_secret,
        raw_body=captured["body"],
        signature=captured["headers"]["x-relayhub-signature"],
        timestamp=captured["headers"]["x-relayhub-timestamp"],
        nonce=captured["headers"]["x-relayhub-nonce"],
    )  # should not raise
    assert captured["headers"]["x-relayhub-event"] == "payment.success"
    assert captured["headers"]["x-relayhub-delivery-id"] == str(job.id)


@pytest.mark.asyncio
async def test_5xx_response_classified_as_transient_and_marks_retrying(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, token, api_key)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="service unavailable")

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert job.status == DeliveryJobStatus.RETRYING.value
    assert job.next_attempt_at is not None
    assert job.attempts[0].error_category == ErrorCategory.TRANSIENT_HTTP_ERROR.value

    endpoint = (await db_session.execute(select(Endpoint).where(Endpoint.id == job.endpoint_id))).scalar_one()
    assert endpoint.consecutive_failure_count == 1


@pytest.mark.asyncio
async def test_404_response_classified_as_permanent_and_marks_failed(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, token, api_key)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert job.status == DeliveryJobStatus.FAILED.value
    assert job.attempts[0].error_category == ErrorCategory.PERMANENT_HTTP_ERROR.value


@pytest.mark.asyncio
async def test_429_classified_as_transient_despite_being_4xx(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, token, api_key)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert job.status == DeliveryJobStatus.RETRYING.value
    assert job.attempts[0].error_category == ErrorCategory.TRANSIENT_HTTP_ERROR.value


@pytest.mark.asyncio
async def test_timeout_classified_correctly(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, token, api_key)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert job.status == DeliveryJobStatus.RETRYING.value
    assert job.attempts[0].error_category == ErrorCategory.TIMEOUT.value


@pytest.mark.asyncio
async def test_connection_error_classified_correctly(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, token, api_key)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert job.status == DeliveryJobStatus.RETRYING.value
    assert job.attempts[0].error_category == ErrorCategory.CONNECTION_ERROR.value


@pytest.mark.asyncio
async def test_ssrf_block_at_delivery_time_prevents_any_http_call(client, unique_email, db_session, monkeypatch):
    """
    Simulates DNS rebinding: the endpoint URL passed registration-time checks (it's a
    normal hostname), but by delivery time it now resolves to a private/metadata IP.
    The connect-time re-check must catch this BEFORE any HTTP request is attempted.
    """
    from app.modules.delivery.connect_time_security import DeliveryBlockedError

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token, url="https://rebinding-target.example.com/hook")
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, token, api_key)

    async def _fake_resolve_blocked(url: str) -> str:
        raise DeliveryBlockedError("Resolved IP '169.254.169.254' for host 'rebinding-target.example.com' is in a blocked range")

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve_blocked)

    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert call_count["n"] == 0, "No HTTP request should ever be sent when the connect-time SSRF check blocks the IP"
    assert job.status == DeliveryJobStatus.FAILED.value
    assert job.attempts[0].error_category == ErrorCategory.SSRF_BLOCKED.value


@pytest.mark.asyncio
async def test_duplicate_claim_is_prevented(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, token, api_key)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)

    # Job is now status=success -- a second worker trying to claim it must be rejected,
    # not silently re-deliver.
    with pytest.raises(JobAlreadyClaimedError):
        await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_no_active_signing_secret_fails_cleanly(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, token, api_key)

    # Simulate a corrupted state: no primary secret exists for this endpoint.
    secret = (
        await db_session.execute(
            select(EndpointSecret).where(EndpointSecret.endpoint_id == uuid.UUID(endpoint_id), EndpointSecret.is_primary.is_(True))
        )
    ).scalar_one()
    secret.is_primary = False
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert job.status == DeliveryJobStatus.FAILED.value
    assert job.attempts[0].error_category == ErrorCategory.SIGNING_ERROR.value


@pytest.mark.asyncio
async def test_delivery_detail_api_exposes_event_payload_and_response_data(client, unique_email, db_session):
    """
    Regression test: DeliveryJobOut previously omitted event_type/payload, and
    DeliveryAttemptOut previously omitted response_headers/response_body_truncated
    even though the DB stored them -- the API just never serialized them. Both are
    required for the frontend's Delivery Detail view (raw payload, response body).
    """
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, token, api_key)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"X-Custom": "value"}, json={"received": True})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()

    assert body["event_type"] == "payment.success"
    assert body["payload"] == {"amount": 4200}

    attempt = body["attempts"][0]
    assert attempt["response_body_truncated"] is not None
    assert "received" in attempt["response_body_truncated"]
    assert "x-custom" in {k.lower() for k in attempt["response_headers"].keys()}
