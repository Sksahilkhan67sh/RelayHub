"""
The actual delivery worker logic. Framework-agnostic on purpose: `execute_delivery_job`
is a plain async function taking an AsyncSession + optional injected httpx client, so it
can be:
  - called directly and fully unit-tested (httpx.MockTransport, no real network, no Celery)
  - wrapped by a Celery task (app/workers/tasks.py) for actual production dispatch
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.realtime_publisher import RealtimePublisher
from app.core.encryption import decrypt_secret
from app.modules.delivery.connect_time_security import DeliveryBlockedError, resolve_and_validate
from app.modules.delivery.models import DeliveryAttempt, DeliveryJob, DeliveryJobStatus, ErrorCategory
from app.modules.delivery.signing import sign
from app.modules.endpoints import service as endpoint_service
from app.modules.endpoints.models import Endpoint, EndpointSecret
from app.modules.events.models import Event
from app.modules.realtime.events import emit_delivery_update
from app.modules.retry.schedule import compute_next_retry_delay

MAX_RESPONSE_BODY_CAPTURE = 4096
TRANSIENT_STATUS_CODES = {408, 429}


class JobAlreadyClaimedError(Exception):
    """Raised when another worker already claimed this job -- not an error, just a signal to skip it."""


async def _claim_job(db: AsyncSession, job_id: uuid.UUID, *, worker_id: str) -> DeliveryJob:
    """
    Compare-and-set claim: only transitions queued/retrying -> processing if no other
    worker has already done so. This is the "avoid duplicate concurrent processing"
    requirement from the spec, implemented as a portable UPDATE ... WHERE status IN (...)
    rather than Postgres-specific SELECT FOR UPDATE SKIP LOCKED, so it behaves
    identically in tests (SQLite) and production (Postgres).

    Also records `claimed_by_worker_id`/`claimed_at` (Phase 2 follow-up) so
    `reconcile_stuck_jobs` can check the claiming worker's actual liveness via
    `worker_heartbeats` instead of relying solely on elapsed time.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(DeliveryJob)
        .where(
            DeliveryJob.id == job_id,
            DeliveryJob.status.in_([DeliveryJobStatus.QUEUED.value, DeliveryJobStatus.RETRYING.value]),
        )
        .values(status=DeliveryJobStatus.PROCESSING.value, claimed_by_worker_id=worker_id, claimed_at=now)
    )
    await db.commit()

    if result.rowcount == 0:
        raise JobAlreadyClaimedError(f"Delivery job {job_id} was already claimed by another worker or is not runnable")

    # tenant-scope: safe - internal Celery worker; job_id came from the queue message only, never
    # from a user request. The job was already created under its owning org at publish time.
    job = (await db.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
    return job


def _classify_response(status_code: int) -> tuple[bool, str]:
    """Returns (is_success, error_category). Success = any 2xx, per spec section 'delivery behavior rules'."""
    if 200 <= status_code < 300:
        return True, ErrorCategory.NONE.value
    if status_code in TRANSIENT_STATUS_CODES or 500 <= status_code < 600:
        return False, ErrorCategory.TRANSIENT_HTTP_ERROR.value
    return False, ErrorCategory.PERMANENT_HTTP_ERROR.value


async def execute_delivery_job(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    worker_id: str = "worker-local",
    region: str = "local",
    http_client: httpx.AsyncClient | None = None,
    realtime_publisher: RealtimePublisher | None = None,
) -> DeliveryJob:
    job = await _claim_job(db, job_id, worker_id=worker_id)

    # tenant-scope: safe - internal worker; event_id comes from the already-tenant-scoped `job`
    # row loaded above, not user input.
    event = (await db.execute(select(Event).where(Event.id == job.event_id))).scalar_one()
    # tenant-scope: safe - internal worker; endpoint_id comes from the already-tenant-scoped `job`
    # row loaded above, not user input.
    endpoint = (await db.execute(select(Endpoint).where(Endpoint.id == job.endpoint_id))).scalar_one()
    primary_secret = (
        await db.execute(
            select(EndpointSecret).where(EndpointSecret.endpoint_id == endpoint.id, EndpointSecret.is_primary.is_(True))
        )
    ).scalar_one_or_none()

    # Realtime "processing" notification -- strictly after _claim_job's own commit
    # above (the CAS UPDATE that actually moved the row to `processing`), so the
    # dashboard shows the transition the instant it's durable, not before.
    # Failure-isolated inside emit_delivery_update: a publish problem here can
    # never affect the delivery attempt this function is about to make.
    if realtime_publisher is not None:
        await emit_delivery_update(
            realtime_publisher,
            organization_id=job.organization_id,
            delivery_job_id=job.id,
            event_id=job.event_id,
            endpoint_id=job.endpoint_id,
            status=DeliveryJobStatus.PROCESSING.value,
            attempt_number=job.attempt_number,
            queued_at=job.queued_at,
            max_attempts=endpoint.max_retry_attempts,
        )

    started_at = datetime.now(timezone.utc)
    start_perf = time.perf_counter()
    job.attempt_number += 1

    async def _finish(
        *, success: bool, http_status: int | None, response_headers: dict, response_body: str | None,
        error_category: str, error_message: str | None, destination_ip: str | None,
    ) -> DeliveryJob:
        completed_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - start_perf) * 1000)

        attempt = DeliveryAttempt(
            delivery_job_id=job.id,
            organization_id=job.organization_id,
            attempt_number=job.attempt_number,
            queued_at=job.queued_at,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            http_status=http_status,
            response_headers=response_headers,
            response_body_truncated=(response_body or "")[:MAX_RESPONSE_BODY_CAPTURE] or None,
            error_category=error_category,
            error_message=error_message,
            worker_id=worker_id,
            region=region,
            destination_ip=destination_ip,
        )
        db.add(attempt)

        if success:
            job.status = DeliveryJobStatus.SUCCESS.value
            job.completed_at = completed_at
            job.next_attempt_at = None
        elif error_category in (
            ErrorCategory.PERMANENT_HTTP_ERROR.value,
            ErrorCategory.SSRF_BLOCKED.value,
            ErrorCategory.SIGNING_ERROR.value,
        ):
            job.status = DeliveryJobStatus.FAILED.value
            job.completed_at = completed_at
            job.next_attempt_at = None
        else:
            delay = compute_next_retry_delay(
                attempt_number=job.attempt_number, max_attempts=endpoint.max_retry_attempts
            )
            if delay is not None:
                job.status = DeliveryJobStatus.RETRYING.value
                job.next_attempt_at = completed_at + delay
            else:
                # Retries exhausted -- hand off to the Dead Letter Queue (full
                # inspect/retry/bulk-action tooling is Phase 3g; this is the transition
                # point where a job stops being "in flight").
                job.status = DeliveryJobStatus.DEAD_LETTER.value
                job.next_attempt_at = None
                job.completed_at = completed_at

        await endpoint_service.record_delivery_result(db, endpoint=endpoint, success=success)
        await db.commit()

        # Realtime terminal/retry-scheduled notification -- strictly after the
        # commit immediately above, so the dashboard never shows a state the
        # database hasn't durably persisted yet (spec Step 9). Covers success,
        # failed, retrying (with next_attempt_at), and dead_letter -- every status
        # this closure can set job.status to.
        if realtime_publisher is not None:
            await emit_delivery_update(
                realtime_publisher,
                organization_id=job.organization_id,
                delivery_job_id=job.id,
                event_id=job.event_id,
                endpoint_id=job.endpoint_id,
                status=job.status,
                attempt_number=job.attempt_number,
                queued_at=job.queued_at,
                max_attempts=endpoint.max_retry_attempts,
                http_status=http_status,
                error_category=error_category if error_category != ErrorCategory.NONE.value else None,
                next_attempt_at=job.next_attempt_at,
                completed_at=job.completed_at,
            )

        if job.status == DeliveryJobStatus.DEAD_LETTER.value:
            from app.common.notification_client import get_notification_dispatcher
            from app.modules.alerts import service as alerts_service
            from app.modules.alerts.models import AlertConditionType

            await alerts_service.trigger_alert(
                db,
                organization_id=job.organization_id,
                condition_type=AlertConditionType.REPEATED_FAILURES.value,
                message=f"Delivery job {job.id} for endpoint '{endpoint.name}' was moved to the dead letter "
                f"queue after {job.attempt_number} attempts. Last error: {error_category}.",
                resource_id=str(job.endpoint_id),
                metadata={"delivery_job_id": str(job.id), "endpoint_id": str(job.endpoint_id), "attempt_number": job.attempt_number},
                notification_dispatcher=get_notification_dispatcher(),
            )

        await db.refresh(job, attribute_names=["attempts"])
        return job

    # Layer 2 SSRF check: re-resolve and validate the IP we are ACTUALLY about to
    # connect to, right now -- not the IP that was valid when the endpoint was
    # registered (see connect_time_security.py docstring).
    try:
        destination_ip = await resolve_and_validate(endpoint.url)
    except DeliveryBlockedError as e:
        return await _finish(
            success=False, http_status=None, response_headers={}, response_body=None,
            error_category=ErrorCategory.SSRF_BLOCKED.value, error_message=str(e), destination_ip=None,
        )

    if not primary_secret:
        return await _finish(
            success=False, http_status=None, response_headers={}, response_body=None,
            error_category=ErrorCategory.SIGNING_ERROR.value, error_message="Endpoint has no active signing secret",
            destination_ip=destination_ip,
        )

    try:
        secret_plaintext = decrypt_secret(primary_secret.encrypted_secret)
    except Exception as e:  # noqa: BLE001 - any decryption failure is a signing error, not a delivery error
        return await _finish(
            success=False, http_status=None, response_headers={}, response_body=None,
            error_category=ErrorCategory.SIGNING_ERROR.value, error_message=f"Failed to decrypt signing secret: {e}",
            destination_ip=destination_ip,
        )

    raw_body = json.dumps(event.payload, separators=(",", ":"), sort_keys=True).encode()
    signature_headers = sign(secret=secret_plaintext, raw_body=raw_body)
    headers = {
        **signature_headers,
        "X-RelayHub-Event": event.event_type,
        "X-RelayHub-Delivery-ID": str(job.id),
        "Content-Type": "application/json",
        **endpoint.custom_headers,
    }

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(verify=endpoint.tls_verification_enabled)
    try:
        response = await client.post(endpoint.url, content=raw_body, headers=headers, timeout=endpoint.timeout_seconds)
    except httpx.TimeoutException as e:
        return await _finish(
            success=False, http_status=None, response_headers={}, response_body=None,
            error_category=ErrorCategory.TIMEOUT.value, error_message=str(e), destination_ip=destination_ip,
        )
    except httpx.ConnectError as e:
        return await _finish(
            success=False, http_status=None, response_headers={}, response_body=None,
            error_category=ErrorCategory.CONNECTION_ERROR.value, error_message=str(e), destination_ip=destination_ip,
        )
    except httpx.HTTPError as e:
        return await _finish(
            success=False, http_status=None, response_headers={}, response_body=None,
            error_category=ErrorCategory.CONNECTION_ERROR.value, error_message=str(e), destination_ip=destination_ip,
        )
    finally:
        if owns_client:
            await client.aclose()

    is_success, error_category = _classify_response(response.status_code)
    return await _finish(
        success=is_success,
        http_status=response.status_code,
        response_headers=dict(response.headers),
        response_body=response.text,
        error_category=error_category,
        error_message=None if is_success else f"Destination returned HTTP {response.status_code}",
        destination_ip=destination_ip,
    )
