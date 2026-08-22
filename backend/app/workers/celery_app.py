import threading

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from app.core.config import settings

celery_app = Celery(
    "relayhub",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

# Phase E fix: the worker process only ever imported the handful of ORM models that
# app/modules/delivery/executor.py happens to import directly (Endpoint, Event,
# DeliveryJob, ...) -- never the full model graph the FastAPI process gets for free
# by importing every router (which transitively imports every module's models).
# SQLAlchemy resolves string-based ForeignKey("organizations.id") targets against
# whatever tables have actually been mapped in-process, so a worker that never
# imported app.modules.auth.models (where Organization lives) raised
# `NoReferencedTableError` on its very first real task -- confirmed live during
# Phase E's end-to-end smoke test (delivery attempted, got as far as writing the
# result, then crashed). Same fix conftest.py already uses for the test suite,
# applied here so the worker process gets it too.
from app.modules.admin import models as _admin_models  # noqa: F401,E402
from app.modules.alerts import models as _alerts_models  # noqa: F401,E402
from app.modules.api_keys import models as _api_keys_models  # noqa: F401,E402
from app.modules.audit import models as _audit_models  # noqa: F401,E402
from app.modules.auth import models as _auth_models  # noqa: F401,E402
from app.modules.billing import models as _billing_models  # noqa: F401,E402
from app.modules.delivery import models as _delivery_models  # noqa: F401,E402
from app.modules.endpoints import models as _endpoints_models  # noqa: F401,E402
from app.modules.events import models as _events_models  # noqa: F401,E402

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,  # don't ack until the task finishes -- a crashed worker's job goes back to the queue
    worker_prefetch_multiplier=4,
    task_reject_on_worker_lost=True,
    beat_schedule={
        "scan-due-retries": {
            "task": "check_due_retries",
            "schedule": 10.0,  # seconds -- frequent enough that 10s-tier retries aren't meaningfully delayed
        },
        "cleanup-expired-delivery-logs": {
            "task": "cleanup_expired_delivery_logs",
            "schedule": 86400.0,  # once a day
        },
        "reconcile-stuck-jobs": {
            "task": "reconcile_stuck_jobs",
            # 60s: frequent enough to catch a crashed worker's abandoned job well
            # within the STUCK_PROCESSING_AFTER heuristic window, cheap enough
            # (a couple of indexed WHERE status = ... UPDATEs) to run every tick.
            "schedule": 60.0,
        },
    },
)

# Phase 2 reliability addition: real worker-fleet liveness, replacing the
# "not tracked yet" gap admin/service.py used to honestly report.
#
# `worker_process_init` fires once per actual worker child process (each prefork
# pool child gets its own call; solo/threads pools get exactly one) -- crucially,
# it is NOT fired by simply importing this module (e.g. the FastAPI process
# imports it lazily via RedisQueueClient.enqueue), so this never spins up a
# heartbeat thread in the API process, only in real `celery worker` processes.
#
# The loop runs in a background daemon thread rather than as a Celery periodic
# task because beat-scheduled tasks run centrally on whichever process runs
# `celery beat` -- they don't naturally give each individual worker process its
# own identity-scoped tick. A plain thread with its own short asyncio lifecycle
# per iteration (matching the same fresh-engine-per-call pattern already used by
# app/workers/tasks.py, for the same asyncpg-event-loop-binding reason) keeps this
# self-contained and out of the request/task hot path.
HEARTBEAT_INTERVAL_SECONDS = 15.0
_heartbeat_stop_event: threading.Event | None = None
_heartbeat_thread: threading.Thread | None = None


def _run_heartbeat_loop(worker_id: str, hostname: str, pid: int, stop_event: threading.Event) -> None:
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.modules.admin import service as admin_service

    async def _beat_once() -> None:
        engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
        session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)
        try:
            async with session_maker() as db:
                await admin_service.upsert_worker_heartbeat(db, worker_id=worker_id, hostname=hostname, pid=pid)
        except Exception:  # noqa: BLE001 - a missed heartbeat write must never crash the worker process itself
            import logging

            logging.getLogger(__name__).exception("worker heartbeat write failed for worker_id=%s", worker_id)
        finally:
            await engine.dispose()

    while not stop_event.is_set():
        asyncio.run(_beat_once())
        stop_event.wait(HEARTBEAT_INTERVAL_SECONDS)


@worker_process_init.connect
def _start_worker_heartbeat(**kwargs) -> None:
    import os
    import socket

    from app.workers.identity import get_worker_id

    global _heartbeat_stop_event, _heartbeat_thread

    # Tracing (OTel follow-up): configured once per worker child process, same
    # lifecycle as the heartbeat thread below. No-op when OTEL_EXPORTER_OTLP_ENDPOINT
    # is unset -- see app/core/tracing.py.
    from app.core.tracing import setup_tracing

    setup_tracing("relayhub-worker")

    hostname = socket.gethostname()
    pid = os.getpid()
    worker_id = get_worker_id()

    _heartbeat_stop_event = threading.Event()
    _heartbeat_thread = threading.Thread(
        target=_run_heartbeat_loop,
        args=(worker_id, hostname, pid, _heartbeat_stop_event),
        name="worker-heartbeat",
        daemon=True,
    )
    _heartbeat_thread.start()


@worker_process_shutdown.connect
def _stop_worker_heartbeat(**kwargs) -> None:
    if _heartbeat_stop_event is not None:
        _heartbeat_stop_event.set()
