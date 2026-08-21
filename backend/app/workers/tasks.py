"""
Celery task entry point. Celery's worker pool is synchronous, but the executor and
all our DB/service code is async SQLAlchemy -- this module is the bridge.

We create a fresh async engine per task invocation (rather than sharing one across
tasks in the worker process) because asyncpg connections are bound to the event loop
that created them, and `asyncio.run()` creates a brand-new loop on every call. Reusing
a pooled connection across different loops raises "attached to a different loop".
The overhead of a fresh engine per task is a known, accepted tradeoff at this stage;
a future hardening pass can switch to a single long-lived event loop per worker
process (e.g. via a dedicated thread with its own loop, wired up in
`worker_process_init`) if connection-setup overhead becomes a measured bottleneck.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.delivery.executor import JobAlreadyClaimedError, execute_delivery_job
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run(job_id: uuid.UUID) -> None:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)
    worker_id = f"{os.uname().nodename if hasattr(os, 'uname') else 'worker'}-{os.getpid()}"

    async with session_maker() as db:
        try:
            job = await execute_delivery_job(db, job_id=job_id, worker_id=worker_id)
            logger.info("delivery_job=%s finished with status=%s", job_id, job.status)
        except JobAlreadyClaimedError:
            logger.info("delivery_job=%s already claimed by another worker, skipping", job_id)
    await engine.dispose()


async def _run_check_due_retries() -> None:
    from app.common.queue_client import get_queue_client
    from app.modules.retry.scheduler import enqueue_due_retries

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_maker() as db:
        due_ids = await enqueue_due_retries(db, queue_client=get_queue_client())
        if due_ids:
            logger.info("re-enqueued %d due retry job(s)", len(due_ids))
    await engine.dispose()


@celery_app.task(name="deliver_webhook", bind=True, max_retries=0)  # retry SCHEDULING is this module's job, not Celery's
def deliver_webhook(self, job_id: str) -> None:
    asyncio.run(_run(uuid.UUID(job_id)))


@celery_app.task(name="check_due_retries")
def check_due_retries() -> None:
    asyncio.run(_run_check_due_retries())


async def _run_cleanup_expired_delivery_logs() -> None:
    from app.modules.logs.retention import cleanup_expired_delivery_logs

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_maker() as db:
        deleted_count = await cleanup_expired_delivery_logs(db)
        logger.info("retention cleanup deleted %d expired delivery job(s)", deleted_count)
    await engine.dispose()


@celery_app.task(name="cleanup_expired_delivery_logs")
def cleanup_expired_delivery_logs_task() -> None:
    asyncio.run(_run_cleanup_expired_delivery_logs())


async def _run_reconcile_stuck_jobs() -> None:
    from app.common.queue_client import get_queue_client
    from app.modules.retry.reconciliation import reconcile_stuck_jobs

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_maker = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_maker() as db:
        result = await reconcile_stuck_jobs(db, queue_client=get_queue_client())
        if result.total_requeued:
            logger.warning(
                "reconciliation: recovered_stuck_processing=%d requeued_stale_queued=%d requeued_missed_retries=%d",
                len(result.recovered_stuck_processing),
                len(result.requeued_stale_queued),
                len(result.requeued_missed_retries),
            )
    await engine.dispose()


@celery_app.task(name="reconcile_stuck_jobs")
def reconcile_stuck_jobs_task() -> None:
    asyncio.run(_run_reconcile_stuck_jobs())
