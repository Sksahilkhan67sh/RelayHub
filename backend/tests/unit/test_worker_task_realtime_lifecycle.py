"""
Regression coverage for the production incident where `deliver_webhook` and
`reconcile_stuck_jobs_task` raised:

    RuntimeError: ... got Future <Future pending> attached to a different loop

Root cause: `app/workers/tasks.py`'s `_run()` / `_run_reconcile_stuck_jobs()`
each run inside their own fresh event loop via `asyncio.run()` (one per Celery
task invocation -- by design, see that module's docstring). They used to source
their realtime publisher from `get_realtime_publisher()`, a process-wide
`@lru_cache` singleton whose underlying `redis.asyncio` client gets bound to
whichever loop first touches it -- so every task after the first one raised
the error above when it tried to use that client from its own, different loop.

The fix: source a brand-new `RedisRealtimePublisher` per task invocation
(`new_realtime_publisher()`), matching the fresh-engine-per-task pattern
already used for the DB engine right next to it, and close it when the task
is done.

These tests don't need a live DB or Redis: they monkeypatch the two things
that would actually touch either (`execute_delivery_job`, `reconcile_stuck_jobs`,
and the realtime publisher factory itself) and assert on the *shape* of the
fix -- a fresh publisher instance per `asyncio.run()` invocation, always
closed afterward -- which is exactly what was missing before.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock

from app.workers import tasks as tasks_module


class _FakePublisher:
    def __init__(self):
        self.aclose = AsyncMock()


def test_run_uses_a_fresh_realtime_publisher_on_every_invocation(monkeypatch):
    created = []

    def _new_realtime_publisher():
        publisher = _FakePublisher()
        created.append(publisher)
        return publisher

    monkeypatch.setattr("app.common.realtime_publisher.new_realtime_publisher", _new_realtime_publisher)

    seen_publishers_in_execute = []

    async def _fake_execute_delivery_job(db, *, job_id, worker_id, realtime_publisher):
        seen_publishers_in_execute.append(realtime_publisher)

        class _Job:
            status = "success"

        return _Job()

    monkeypatch.setattr(tasks_module, "execute_delivery_job", _fake_execute_delivery_job)

    # Two separate `asyncio.run()` calls -- exactly what two consecutive
    # `deliver_webhook` Celery task executions look like: each gets its own,
    # brand-new event loop.
    asyncio.run(tasks_module._run(uuid.uuid4()))
    asyncio.run(tasks_module._run(uuid.uuid4()))

    assert len(created) == 2, "each asyncio.run() invocation must get its own realtime publisher"
    assert created[0] is not created[1]
    assert seen_publishers_in_execute == created, "the fresh publisher must be the one actually used for delivery"
    created[0].aclose.assert_awaited_once()
    created[1].aclose.assert_awaited_once()


def test_reconcile_stuck_jobs_uses_a_fresh_realtime_publisher_on_every_invocation(monkeypatch):
    created = []

    def _new_realtime_publisher():
        publisher = _FakePublisher()
        created.append(publisher)
        return publisher

    monkeypatch.setattr("app.common.realtime_publisher.new_realtime_publisher", _new_realtime_publisher)

    seen_publishers_in_reconcile = []

    class _Result:
        total_requeued = 0
        recovered_stuck_processing = []
        requeued_stale_queued = []
        requeued_missed_retries = []

    async def _fake_reconcile_stuck_jobs(db, *, queue_client, realtime_publisher):
        seen_publishers_in_reconcile.append(realtime_publisher)
        return _Result()

    monkeypatch.setattr("app.modules.retry.reconciliation.reconcile_stuck_jobs", _fake_reconcile_stuck_jobs)
    monkeypatch.setattr("app.common.queue_client.get_queue_client", lambda: object())

    asyncio.run(tasks_module._run_reconcile_stuck_jobs())
    asyncio.run(tasks_module._run_reconcile_stuck_jobs())

    assert len(created) == 2, "each asyncio.run() invocation must get its own realtime publisher"
    assert created[0] is not created[1]
    assert seen_publishers_in_reconcile == created
    created[0].aclose.assert_awaited_once()
    created[1].aclose.assert_awaited_once()
