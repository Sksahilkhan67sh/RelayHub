import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.realtime_publisher import (
    InMemoryRealtimePublisher,
    RedisRealtimePublisher,
    channel_for_org,
    get_realtime_publisher,
    new_realtime_publisher,
)
from app.modules.realtime.events import emit_delivery_update


def _fake_redis_client() -> MagicMock:
    client = MagicMock()
    client.aclose = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_new_realtime_publisher_returns_a_fresh_instance_each_call(monkeypatch):
    """Regression test for the "attached to a different loop" production bug:

    Celery tasks each run in their own fresh `asyncio.run()` loop, so anything
    they use that holds an asyncio-bound resource (like a redis.asyncio client)
    must be constructed fresh per task, never shared via a cached singleton --
    see app/workers/tasks.py's `_run()`/`_run_reconcile_stuck_jobs()`, which
    call this instead of the process-wide `get_realtime_publisher()`.
    """
    created_clients = []

    def _from_url(url):
        client = _fake_redis_client()
        created_clients.append(client)
        return client

    monkeypatch.setattr("redis.asyncio.from_url", _from_url)

    first = new_realtime_publisher()
    second = new_realtime_publisher()

    assert isinstance(first, RedisRealtimePublisher)
    assert first is not second, "each call must return a brand-new instance, not a cached singleton"
    assert len(created_clients) == 2, "each instance must have its own underlying redis client"

    await first.aclose()
    await second.aclose()
    created_clients[0].aclose.assert_awaited_once()
    created_clients[1].aclose.assert_awaited_once()


def test_get_realtime_publisher_remains_a_cached_singleton(monkeypatch):
    """`get_realtime_publisher()` is for the single-event-loop FastAPI process
    only -- it must stay cached there (that's correct and intentional), in
    contrast to `new_realtime_publisher()` above."""
    monkeypatch.setattr("redis.asyncio.from_url", lambda url: _fake_redis_client())
    get_realtime_publisher.cache_clear()
    try:
        assert get_realtime_publisher() is get_realtime_publisher()
    finally:
        get_realtime_publisher.cache_clear()


@pytest.mark.asyncio
async def test_publish_records_payload_and_scopes_by_org():
    publisher = InMemoryRealtimePublisher()
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    await publisher.publish(org_a, {"hello": "a"})
    await publisher.publish(org_b, {"hello": "b"})

    assert publisher.published == [(org_a, {"hello": "a"}), (org_b, {"hello": "b"})]


@pytest.mark.asyncio
async def test_subscription_only_receives_its_own_org_events():
    publisher = InMemoryRealtimePublisher()
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    sub_a = publisher.subscribe(org_a)
    messages_iter = sub_a.messages()

    await publisher.publish(org_b, {"leak": "should not appear"})
    await publisher.publish(org_a, {"real": "event"})

    received = await anext(messages_iter)
    assert received == {"real": "event"}
    await sub_a.close()


@pytest.mark.asyncio
async def test_emit_delivery_update_publishes_full_contract():
    publisher = InMemoryRealtimePublisher()
    org_id = uuid.uuid4()
    job_id = uuid.uuid4()
    event_id = uuid.uuid4()
    endpoint_id = uuid.uuid4()
    queued_at = datetime.now(timezone.utc)

    await emit_delivery_update(
        publisher,
        organization_id=org_id,
        delivery_job_id=job_id,
        event_id=event_id,
        endpoint_id=endpoint_id,
        status="success",
        attempt_number=1,
        queued_at=queued_at,
        max_attempts=5,
        http_status=200,
        error_category=None,
    )

    assert len(publisher.published) == 1
    published_org, payload = publisher.published[0]
    assert published_org == org_id
    assert payload["type"] == "delivery.updated"
    assert payload["delivery_job_id"] == str(job_id)
    assert payload["event_id"] == str(event_id)
    assert payload["endpoint_id"] == str(endpoint_id)
    assert payload["organization_id"] == str(org_id)
    assert payload["status"] == "success"
    assert payload["attempt_number"] == 1
    assert payload["max_attempts"] == 5
    assert payload["http_status"] == 200
    assert payload["error_category"] is None
    assert payload["queued_at"] == queued_at.isoformat()
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_emit_delivery_update_never_raises_when_publisher_fails():
    class ExplodingPublisher:
        async def publish(self, organization_id, payload):
            raise ConnectionError("redis is down")

        def subscribe(self, organization_id):
            raise NotImplementedError

    # Must not raise -- realtime failures are isolated from delivery/API code,
    # per spec Step 20 ("realtime failure cannot break delivery").
    await emit_delivery_update(
        ExplodingPublisher(),
        organization_id=uuid.uuid4(),
        delivery_job_id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        endpoint_id=uuid.uuid4(),
        status="success",
        attempt_number=1,
        queued_at=datetime.now(timezone.utc),
    )


def test_channel_naming_is_org_scoped():
    org_id = uuid.uuid4()
    assert channel_for_org(org_id) == f"relayhub:realtime:org:{org_id}"
