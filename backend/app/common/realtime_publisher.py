"""
Realtime notification transport for delivery status updates.

Same shape as common/queue_client.py, common/notification_client.py, and
common/rate_limiter.py: a Protocol, a real Redis pub/sub implementation, and an
injectable in-memory implementation so callers stay fully unit-testable without a
live Redis instance.

This is NOT a second queue and NOT a source of truth. `delivery_jobs` /
`delivery_attempts` in PostgreSQL remain authoritative -- see
app/modules/realtime/events.py's module docstring for how callers are expected to
use this (always after a DB commit, and always failure-isolated).

Channel naming is organization-scoped (`relayhub:realtime:org:{organization_id}`)
so that Redis pub/sub -- not client-side filtering -- is what prevents one
organization from ever receiving another organization's delivery events. A
subscriber only ever subscribes to the single channel derived from its own
authenticated `organization_id`; it has no way to name a different one.
"""

from __future__ import annotations

import json
import logging
import uuid
from functools import lru_cache
from typing import Any, AsyncIterator, Protocol

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "relayhub:realtime:org:"


def channel_for_org(organization_id: uuid.UUID) -> str:
    return f"{CHANNEL_PREFIX}{organization_id}"


class RealtimePublisher(Protocol):
    async def publish(self, organization_id: uuid.UUID, payload: dict[str, Any]) -> None: ...

    def subscribe(self, organization_id: uuid.UUID) -> "RealtimeSubscription": ...


class RealtimeSubscription(Protocol):
    """An open subscription to one organization's realtime channel."""

    def messages(self) -> AsyncIterator[dict[str, Any]]: ...

    async def close(self) -> None: ...


class RedisRealtimePublisher:
    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as redis

        # Reuses settings.REDIS_URL (DB 0) -- the same database app/core/health.py
        # already pings for the readiness probe, and distinct from the Celery
        # broker/result-backend DBs (1/2). Pub/sub and rate-limiter keys/channels
        # don't collide: rate limiter uses `relayhub:ratelimit:*` keys, this uses
        # `relayhub:realtime:org:*` pub/sub channels.
        self._redis_url = redis_url
        self._redis = redis.from_url(redis_url)

    async def publish(self, organization_id: uuid.UUID, payload: dict[str, Any]) -> None:
        channel = channel_for_org(organization_id)
        message = json.dumps(payload, default=str)
        await self._redis.publish(channel, message)

    def subscribe(self, organization_id: uuid.UUID) -> "RealtimeSubscription":
        return RedisRealtimeSubscription(self._redis, organization_id)


class RedisRealtimeSubscription:
    def __init__(self, redis: Any, organization_id: uuid.UUID) -> None:
        self._redis = redis
        self._pubsub = redis.pubsub()
        self._channel = channel_for_org(organization_id)
        self._subscribed = False

    async def messages(self) -> AsyncIterator[dict[str, Any]]:
        if not self._subscribed:
            await self._pubsub.subscribe(self._channel)
            self._subscribed = True
        # ignore_subscribe_messages skips the subscribe-confirmation message itself;
        # timeout=None with get_message's own internal poll keeps this a plain async
        # generator the route can `async for` over without busy-looping.
        while True:
            message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                yield {"type": "keepalive"}
                continue
            try:
                data = json.loads(message["data"])
            except (TypeError, ValueError, KeyError):  # noqa: BLE001 - a malformed message must never kill the stream
                logger.warning("realtime: dropped malformed pub/sub message on %s", self._channel)
                continue
            yield data

    async def close(self) -> None:
        if self._subscribed:
            await self._pubsub.unsubscribe(self._channel)
        await self._pubsub.aclose()


class InMemoryRealtimePublisher:
    """
    Used in tests and local dev without Redis. Records every publish() call (so
    tests can assert on exact payloads / channel scoping) and fans out to any
    currently-open InMemorySubscription for the same organization, so integration
    tests can exercise the SSE route end-to-end against a real ASGI transport
    without a live Redis broker.
    """

    def __init__(self) -> None:
        self.published: list[tuple[uuid.UUID, dict[str, Any]]] = []
        self._subscribers: dict[uuid.UUID, list["_InMemoryQueue"]] = {}

    async def publish(self, organization_id: uuid.UUID, payload: dict[str, Any]) -> None:
        self.published.append((organization_id, payload))
        for queue in self._subscribers.get(organization_id, []):
            await queue.put(payload)

    def subscribe(self, organization_id: uuid.UUID) -> "RealtimeSubscription":
        queue: "_InMemoryQueue" = _InMemoryQueue()
        self._subscribers.setdefault(organization_id, []).append(queue)
        return InMemoryRealtimeSubscription(self, organization_id, queue)

    def _unsubscribe(self, organization_id: uuid.UUID, queue: "_InMemoryQueue") -> None:
        subs = self._subscribers.get(organization_id, [])
        if queue in subs:
            subs.remove(queue)


class _InMemoryQueue:
    def __init__(self) -> None:
        import asyncio

        self._queue: "asyncio.Queue[dict[str, Any]]" = asyncio.Queue()

    async def put(self, item: dict[str, Any]) -> None:
        await self._queue.put(item)

    async def get(self, timeout: float) -> dict[str, Any] | None:
        import asyncio

        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


class InMemoryRealtimeSubscription:
    def __init__(self, publisher: InMemoryRealtimePublisher, organization_id: uuid.UUID, queue: "_InMemoryQueue") -> None:
        self._publisher = publisher
        self._organization_id = organization_id
        self._queue = queue
        self._closed = False

    async def messages(self) -> AsyncIterator[dict[str, Any]]:
        while not self._closed:
            item = await self._queue.get(timeout=1.0)
            if item is None:
                yield {"type": "keepalive"}
                continue
            yield item

    async def close(self) -> None:
        self._closed = True
        self._publisher._unsubscribe(self._organization_id, self._queue)


@lru_cache
def get_realtime_publisher() -> RealtimePublisher:
    from app.core.config import settings

    return RedisRealtimePublisher(settings.REDIS_URL)
