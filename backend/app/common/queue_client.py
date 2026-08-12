"""
Abstraction over "hand this delivery job to a worker".

Why an interface instead of calling Celery directly from the event service: it
keeps the event/retry-scheduling code testable without a live Redis/Celery broker
in CI (`InMemoryQueueClient`), the same way a test suite doesn't spin up a live
Stripe account either. `RedisQueueClient` is the real, production implementation.

Phase E fix: this used to RPUSH the job id onto a plain Redis list
(`relayhub:delivery_queue`) that nothing in the codebase ever consumed -- the
Celery worker (app/workers/tasks.py) only runs tasks that are actually dispatched
to it via Celery's own broker, and no process here ever popped that list and
called `deliver_webhook.delay(...)`. That meant every published event queued a
DeliveryJob row in Postgres that no worker would ever pick up. Confirmed live
during Phase E's end-to-end smoke test: publishing an event with a running
`celery worker` process left the job stuck in `status=queued` indefinitely.
Fixed by dispatching straight to Celery's own broker (`send_task`, by name, to
avoid an import cycle with app.workers.tasks) instead of a second, uncomsumed
queue -- one real queue, matching the architecture Celery already provides.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Protocol


class QueueClient(Protocol):
    async def enqueue(self, job_id: uuid.UUID) -> None: ...


class RedisQueueClient:
    def __init__(self, redis_url: str) -> None:
        # redis_url is accepted for interface/config-injection compatibility (and
        # because a broker-availability check could use it), but dispatch itself
        # goes through Celery's own broker connection (settings.CELERY_BROKER_URL),
        # configured once in app.workers.celery_app -- not a second Redis client.
        self._redis_url = redis_url

    async def enqueue(self, job_id: uuid.UUID) -> None:
        from app.workers.celery_app import celery_app

        celery_app.send_task("deliver_webhook", args=[str(job_id)])


class InMemoryQueueClient:
    """Used in tests and local dev without Redis running. Records enqueued job IDs in order."""

    def __init__(self) -> None:
        self.queued: list[uuid.UUID] = []

    async def enqueue(self, job_id: uuid.UUID) -> None:
        self.queued.append(job_id)


@lru_cache
def get_queue_client() -> QueueClient:
    from app.core.config import settings

    return RedisQueueClient(settings.REDIS_URL)
