"""
The realtime event contract for delivery status updates, and the one function
every state-transition call site in this phase uses to publish one.

Contract (stable, additive-only -- do not rename or remove a field without
bumping every frontend consumer in lockstep):

    {
      "type": "delivery.updated",
      "delivery_job_id": "<uuid>",
      "event_id": "<uuid>",
      "endpoint_id": "<uuid>",
      "organization_id": "<uuid>",
      "status": "queued" | "processing" | "success" | "retrying" | "failed" | "dead_letter",
      "attempt_number": int,
      "max_attempts": int | null,
      "http_status": int | null,
      "error_category": str | null,
      "queued_at": "<iso8601>",
      "next_attempt_at": "<iso8601> | null",
      "completed_at": "<iso8601> | null",
      "timestamp": "<iso8601>"   # when this notification was emitted, not a DB field
    }

Every field name and every possible `status` value matches
`app.modules.delivery.models.DeliveryJobStatus` exactly -- nothing here is
invented. `max_attempts` is the endpoint's effective `max_retry_attempts`
(same value the REST `DeliveryJobOut`/`DeliveryLogEntryOut` schemas already
expose); it is `None` only for the rare emit sites (reconciliation's bulk
recovery path) that don't have the endpoint row loaded and don't want an extra
query just for a display nicety the frontend already has cached from its last
REST fetch.

CRITICAL: `emit_delivery_update` must be called strictly AFTER the caller's own
`await db.commit()` for the transition it's reporting -- never before, and never
in a way that could run if the commit didn't happen. It never raises: any
publisher failure (Redis down, network blip) is logged and swallowed, because a
realtime notification failing must never turn an already-durably-committed
delivery state change into a request/task failure (spec: "realtime is
observability/UX infrastructure, not delivery infrastructure").
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.common.realtime_publisher import RealtimePublisher

logger = logging.getLogger(__name__)


async def emit_delivery_update(
    publisher: RealtimePublisher,
    *,
    organization_id: uuid.UUID,
    delivery_job_id: uuid.UUID,
    event_id: uuid.UUID,
    endpoint_id: uuid.UUID,
    status: str,
    attempt_number: int,
    queued_at: datetime,
    max_attempts: int | None = None,
    http_status: int | None = None,
    error_category: str | None = None,
    next_attempt_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> None:
    payload: dict[str, Any] = {
        "type": "delivery.updated",
        "delivery_job_id": str(delivery_job_id),
        "event_id": str(event_id),
        "endpoint_id": str(endpoint_id),
        "organization_id": str(organization_id),
        "status": status,
        "attempt_number": attempt_number,
        "max_attempts": max_attempts,
        "http_status": http_status,
        "error_category": error_category,
        "queued_at": queued_at.isoformat(),
        "next_attempt_at": next_attempt_at.isoformat() if next_attempt_at else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        await publisher.publish(organization_id, payload)
        from app.core.metrics import realtime_events_published_total

        realtime_events_published_total.labels(status=status).inc()
    except Exception:  # noqa: BLE001 - realtime publish failure must never propagate to the caller
        logger.exception(
            "realtime: failed to publish delivery.updated for delivery_job=%s (status=%s) -- "
            "delivery state itself is already durably committed and unaffected",
            delivery_job_id, status,
        )
        try:
            from app.core.metrics import realtime_publish_failures_total

            realtime_publish_failures_total.inc()
        except Exception:  # noqa: BLE001 - metrics must never be able to break this failure-isolation path either
            pass
