"""
Integration tests for the realtime SSE endpoint.

Environment note: httpx's `ASGITransport` (the transport `tests/conftest.py`'s
`client` fixture uses for every other integration test) buffers an ASGI app's
ENTIRE response body before returning anything to the caller (see
`httpx._transports.asgi.ASGITransport.handle_async_request` -- it awaits
`self.app(scope, receive, send)` to full completion, then wraps the fully
collected `body_parts` in a `Response`). That's fine for every other endpoint in
this codebase, which all return a complete body promptly, but it cannot be used
to exercise a genuinely long-lived, indefinitely-open SSE stream: doing so simply
hangs `client.stream(...)` for however long the generator runs, which is forever
here (confirmed: attempting the naive `async with client.stream(...)` approach
hung until pytest-timeout killed it). This is a real, environment-level
limitation of the test transport, not a defect in the endpoint.

To still test the actual production code path -- auth parsing, org-scoped
subscription, tenant isolation, and SSE event formatting -- these tests call
`stream_delivery_updates` (the route coroutine) directly with an explicit
`token`/`publisher`, which bypasses FastAPI's dependency-injection layer (whose
job is only to resolve those same arguments from the request) but exercises
every line of the endpoint's own logic. The returned `StreamingResponse`'s
`body_iterator` (the real `event_stream()` async generator defined inside the
route) is then driven manually, a bounded number of times, each guarded by
`asyncio.wait_for` so a genuine regression fails fast instead of hanging the
suite -- rather than run to completion the way `ASGITransport` would require.
"""

import asyncio
import json
import uuid

import httpx
import pytest
from starlette.requests import Request

from app.modules.delivery import executor as executor_module
from app.modules.delivery.executor import execute_delivery_job
from app.modules.realtime.routes import stream_delivery_updates
from tests.conftest import create_api_key, create_endpoint, register_and_get_token


@pytest.fixture(autouse=True)
def patch_connect_time_resolution(monkeypatch):
    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve)


def _fake_request(*, headers: dict[str, str] | None = None) -> Request:
    """A minimal Starlette Request good enough for the route's own logic
    (header reads, `is_disconnected()`) without a real ASGI server. `receive`
    never actually resolves within the immediately-cancelled scope
    `Request.is_disconnected()` uses internally, so it always reports "not
    disconnected" here -- exactly like a real, still-open client connection."""
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {"type": "http", "method": "GET", "headers": raw_headers, "query_string": b""}

    async def _receive():
        await asyncio.sleep(3600)
        return {"type": "http.disconnect"}  # pragma: no cover - never actually reached

    return Request(scope, receive=_receive)


async def _drain_events(body_iterator, *, count: int, timeout: float = 5.0) -> list[dict]:
    """Pulls `count` real `delivery.updated` SSE frames (skipping the leading
    `retry:` hint and any keepalive comments -- which arrive roughly every
    second and would otherwise keep resetting a per-call timeout forever), all
    bounded by one overall `timeout` so a genuine regression (or, for the
    tenant-isolation test, a genuine absence of any event) fails deterministically
    instead of hanging the suite."""

    async def _collect() -> list[dict]:
        events: list[dict] = []
        while len(events) < count:
            chunk = await body_iterator.__anext__()
            if isinstance(chunk, bytes):
                chunk = chunk.decode()
            for line in chunk.splitlines():
                if line.startswith("data:"):
                    events.append(json.loads(line[len("data:"):].strip()))
        return events

    return await asyncio.wait_for(_collect(), timeout=timeout)


@pytest.mark.asyncio
async def test_stream_rejects_missing_token(client):
    resp = await client.get("/v1/realtime/deliveries/stream")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stream_rejects_invalid_token(client):
    resp = await client.get("/v1/realtime/deliveries/stream", params={"token": "not-a-real-token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stream_accepts_token_via_header_too(client, unique_email):
    """Non-browser callers (curl, CLI, server-to-server) can use a normal
    Authorization header instead of the query-string token EventSource needs."""
    token = await register_and_get_token(client, unique_email)
    request = _fake_request(headers={"authorization": f"Bearer {token}"})

    response = await stream_delivery_updates(request, token=None, publisher=client.fake_realtime)
    assert response.status_code == 200
    assert response.media_type == "text/event-stream"
    await response.body_iterator.aclose()


@pytest.mark.asyncio
async def test_stream_receives_queued_event_after_publish(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    request = _fake_request()
    response = await stream_delivery_updates(request, token=token, publisher=client.fake_realtime)
    assert response.status_code == 200

    try:
        publish_resp = await client.post(
            "/v1/events",
            json={"event": "payment.success", "payload": {"amount": 100}, "idempotency_key": str(uuid.uuid4())},
            headers={"X-RelayHub-Api-Key": api_key},
        )
        assert publish_resp.status_code == 201
        job_id = publish_resp.json()["delivery_jobs"][0]["id"]

        events = await _drain_events(response.body_iterator, count=1)
    finally:
        await response.body_iterator.aclose()

    assert events[0]["type"] == "delivery.updated"
    assert events[0]["delivery_job_id"] == job_id
    assert events[0]["endpoint_id"] == endpoint_id
    assert events[0]["status"] == "queued"
    assert events[0]["attempt_number"] == 0


@pytest.mark.asyncio
async def test_stream_never_receives_another_organizations_events(client, unique_email, db_session):
    """Tenant isolation, verified at the realtime transport level (spec Step 32)
    -- not just visually: org A's stream must never see org B's delivery.updated
    event, because publish() only ever fans out to subscribers of the matching
    organization_id (see InMemoryRealtimePublisher / RedisRealtimePublisher's
    org-scoped channel naming)."""
    token_a = await register_and_get_token(client, unique_email)
    token_b = await register_and_get_token(client, f"other-{uuid.uuid4().hex[:8]}@example.com")
    endpoint_b = await create_endpoint(client, token_b)
    api_key_b = await create_api_key(client, token_b)

    request_a = _fake_request()
    response_a = await stream_delivery_updates(request_a, token=token_a, publisher=client.fake_realtime)

    try:
        publish_resp = await client.post(
            "/v1/events",
            json={"event": "payment.success", "payload": {"amount": 100}, "idempotency_key": str(uuid.uuid4())},
            headers={"X-RelayHub-Api-Key": api_key_b},
        )
        assert publish_resp.status_code == 201
        assert publish_resp.json()["delivery_jobs"][0]["endpoint_id"] == endpoint_b

        # Org A's stream must time out waiting for an event that was never meant
        # for it -- receiving anything here would be a tenant-isolation failure.
        with pytest.raises(asyncio.TimeoutError):
            await _drain_events(response_a.body_iterator, count=1, timeout=2.5)
    finally:
        await response_a.body_iterator.aclose()


@pytest.mark.asyncio
async def test_stream_receives_full_lifecycle_success(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    def _always_200(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    request = _fake_request()
    response = await stream_delivery_updates(request, token=token, publisher=client.fake_realtime)

    try:
        publish_resp = await client.post(
            "/v1/events",
            json={"event": "payment.success", "payload": {"amount": 100}, "idempotency_key": str(uuid.uuid4())},
            headers={"X-RelayHub-Api-Key": api_key},
        )
        job_id = uuid.UUID(publish_resp.json()["delivery_jobs"][0]["id"])

        queued_events = await _drain_events(response.body_iterator, count=1)
        assert queued_events[0]["status"] == "queued"

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_always_200))
        job = await execute_delivery_job(
            db_session, job_id=job_id, http_client=mock_client, realtime_publisher=client.fake_realtime
        )
        await mock_client.aclose()
        assert job.status == "success"

        lifecycle_events = await _drain_events(response.body_iterator, count=2)
    finally:
        await response.body_iterator.aclose()

    assert lifecycle_events[0]["status"] == "processing"
    assert lifecycle_events[1]["status"] == "success"
    assert lifecycle_events[1]["http_status"] == 200
