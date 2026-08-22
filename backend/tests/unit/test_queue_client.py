"""
Phase E regression test: RedisQueueClient.enqueue used to RPUSH onto a Redis list
that nothing ever consumed (see app/common/queue_client.py's module docstring and
docs/architecture/README.md's Phase E note). This pins the fixed behavior --
dispatching straight to Celery's own broker -- so a future change can't silently
reintroduce a dead queue.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.common.queue_client import RedisQueueClient


@pytest.mark.asyncio
async def test_enqueue_dispatches_to_celery_broker_not_a_separate_redis_list():
    client = RedisQueueClient(redis_url="redis://localhost:6379/0")
    job_id = uuid.uuid4()

    fake_celery_app = MagicMock()
    with patch("app.workers.celery_app.celery_app", fake_celery_app):
        await client.enqueue(job_id)

    fake_celery_app.send_task.assert_called_once_with("deliver_webhook", args=[str(job_id)], headers=None)
