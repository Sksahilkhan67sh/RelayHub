"""
Phase 3 observability additions: DB pool gauges and Celery task-failure
counter. Not a comprehensive test of app/core/metrics.py as a whole (the
existing queue-depth/worker-health/delivery-metrics gauges predate this
phase and aren't touched here) -- scoped to what changed.
"""
from app.core.metrics import celery_task_failures_total


def test_refresh_db_pool_gauges_does_not_raise_on_sqlite():
    """The test suite runs on SQLite (StaticPool), which has no
    checkedout()/size() -- must skip cleanly, not crash the whole /metrics
    scrape over a pool type mismatch."""
    from app.core.metrics import _refresh_db_pool_gauges

    _refresh_db_pool_gauges()  # no assertion needed beyond "doesn't raise"


def test_task_failure_signal_increments_counter_and_logs(caplog):
    import logging

    from app.workers.celery_app import _record_task_failure

    class _FakeSender:
        name = "deliver_webhook"

    before = celery_task_failures_total.labels(task_name="deliver_webhook")._value.get()

    with caplog.at_level(logging.ERROR, logger="app.workers.celery_app"):
        _record_task_failure(sender=_FakeSender(), task_id="task-123", exception=RuntimeError("boom"))

    after = celery_task_failures_total.labels(task_name="deliver_webhook")._value.get()
    assert after == before + 1
    assert any("celery_task_failed" in r.message and "deliver_webhook" in r.message for r in caplog.records)


def test_task_failure_signal_handles_missing_sender_gracefully(caplog):
    import logging

    from app.workers.celery_app import _record_task_failure

    with caplog.at_level(logging.ERROR, logger="app.workers.celery_app"):
        _record_task_failure(sender=None, task_id="task-456", exception=ValueError("x"))

    assert any("unknown" in r.message for r in caplog.records)
