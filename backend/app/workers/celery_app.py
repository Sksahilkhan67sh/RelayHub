from celery import Celery

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
