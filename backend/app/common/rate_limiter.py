"""
Sliding-window-log rate limiting, per spec section 13.

Same shape as common/queue_client.py and common/notification_client.py: a Protocol,
a real Redis-backed implementation, and an injectable in-memory implementation so
rate-limit logic is fully unit-testable without live Redis.

Sliding window log (not fixed bucket) is used deliberately: a fixed-window counter
lets a client burst up to 2x the limit right at a window boundary (e.g. 100 requests
in the last second of one minute, another 100 in the first second of the next). A
sliding window -- tracking individual request timestamps and counting how many fall
within the trailing N seconds -- doesn't have that gap.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Protocol

MINUTE_SECONDS = 60
HOUR_SECONDS = 3600
DAY_SECONDS = 86400


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: datetime
    window_seconds: int


class RateLimiter(Protocol):
    async def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult: ...


class RedisRateLimiter:
    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as redis

        self._redis = redis.from_url(redis_url)

    async def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.time()
        window_start = now - window_seconds
        redis_key = f"relayhub:ratelimit:{key}:{window_seconds}"

        # Atomic-ish via pipeline: trim anything outside the window, record this
        # request (unique member so simultaneous requests in the same millisecond
        # don't collide and get deduplicated by ZADD), count, and set a TTL so idle
        # keys don't accumulate forever.
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zadd(redis_key, {str(uuid.uuid4()): now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, window_seconds)
        _, _, count, _ = await pipe.execute()

        allowed = count <= limit
        remaining = max(0, limit - count)
        reset_at = datetime.fromtimestamp(now + window_seconds, tz=timezone.utc)
        return RateLimitResult(allowed=allowed, limit=limit, remaining=remaining, reset_at=reset_at, window_seconds=window_seconds)


class InMemoryRateLimiter:
    """
    Used in tests and local dev without Redis. NOT safe across multiple processes
    (each process would have its own counters) -- that's exactly what the Redis
    implementation is for in production, where all API instances must share one view
    of a client's request count.
    """

    def __init__(self) -> None:
        self._store: dict[str, list[float]] = {}

    async def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.time()
        window_start = now - window_seconds
        store_key = f"{key}:{window_seconds}"

        timestamps = self._store.setdefault(store_key, [])
        timestamps[:] = [t for t in timestamps if t > window_start]
        timestamps.append(now)
        count = len(timestamps)

        allowed = count <= limit
        remaining = max(0, limit - count)
        reset_at = datetime.fromtimestamp(now + window_seconds, tz=timezone.utc)
        return RateLimitResult(allowed=allowed, limit=limit, remaining=remaining, reset_at=reset_at, window_seconds=window_seconds)

    def reset(self) -> None:
        self._store.clear()


@lru_cache
def get_rate_limiter() -> RateLimiter:
    from app.core.config import settings

    return RedisRateLimiter(settings.REDIS_URL)
