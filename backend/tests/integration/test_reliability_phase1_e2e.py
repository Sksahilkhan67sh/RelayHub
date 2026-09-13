"""
Phase 1 production reliability hardening: E2E scenarios explicitly required by
the audit brief that were not already covered end-to-end elsewhere.

Context on what's already covered, so this file doesn't duplicate it:
  - single-attempt classification of 429/5xx/timeout/connection-error
    (test_delivery_executor.py)
  - generic (constant-failure) multi-attempt retry accumulation, exhaustion to
    DEAD_LETTER, and success-after-a-single-retry
    (test_delivery_attempt_ux.py, test_retry_engine.py)
  - DLQ replay resets state and re-enqueues, double-retry safety
    (test_dlq.py)
  - CAS duplicate-claim rejection (test_delivery_executor.py)
  - reconciliation / worker-crash recovery (test_reconciliation.py)

What's new here:
  - literal mixed-status-code multi-attempt sequences ending in SUCCESS
    (429, 429, 200 and a timeout/connection-error recovering on retry),
    verified against the actual delivery_attempts rows, not just the job's
    final state
  - DLQ replay's effect on attempt ordering (attempt_number resets per
    replay -- see app/modules/delivery/models.py's DeliveryJob.attempts
    docstring -- so this proves `job.attempts` still comes back in true
    chronological order)
  - cross-tenant denial for delivery detail and DLQ, which had no regression
    coverage despite both underlying queries already being tenant-scoped
"""

import uuid

import httpx
import pytest
from sqlalchemy import select

from app.modules.delivery import executor as executor_module
from app.modules.delivery.executor import execute_delivery_job
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus
from tests.conftest import create_api_key, create_endpoint, register_and_get_token


@pytest.fixture(autouse=True)
def patch_connect_time_resolution(monkeypatch):
    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve)


async def _publish_and_get_job_id(client, api_key) -> uuid.UUID:
    resp = await client.post(
        "/v1/events",
        json={"event": "payment.success", "payload": {"amount": 4200}},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["delivery_jobs"][0]["id"])


def _mock_client(status_code: int | None = None, *, exc: Exception | None = None) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if exc is not None:
            raise exc
        return httpx.Response(status_code, text="body")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _requeue(db_session, job_id: uuid.UUID) -> None:
    """What a real retry (via the scanner + queue) does to a RETRYING job before
    a worker claims it again: flips it back to QUEUED. Bypassing the scanner/
    queue hop itself here since that round-trip is already proven separately by
    test_full_retry_loop_scanner_actually_triggers_second_attempt."""
    job_row = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
    job_row.status = DeliveryJobStatus.QUEUED.value
    await db_session.commit()


# ---------------------------------------------------------------------------
# Required scenario: 429 -> 429 -> 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_429_429_200_full_recovery_e2e(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    expected_sequence = [(429, DeliveryJobStatus.RETRYING), (429, DeliveryJobStatus.RETRYING), (200, DeliveryJobStatus.SUCCESS)]
    for expected_attempt_number, (status_code, expected_status) in enumerate(expected_sequence, start=1):
        mock_client = _mock_client(status_code)
        job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
        await mock_client.aclose()
        assert job.attempt_number == expected_attempt_number
        assert job.status == expected_status.value
        if job.status != DeliveryJobStatus.SUCCESS.value:
            await _requeue(db_session, job_id)

    # Verify against the actual delivery_attempts rows, not just the job's final
    # state -- no attempt disappeared, each has the right status code recorded.
    job = (
        await db_session.execute(
            select(DeliveryJob).where(DeliveryJob.id == job_id)
        )
    ).scalar_one()
    await db_session.refresh(job, attribute_names=["attempts"])
    assert [a.http_status for a in job.attempts] == [429, 429, 200]
    assert [a.attempt_number for a in job.attempts] == [1, 2, 3]
    assert job.status == DeliveryJobStatus.SUCCESS.value
    assert job.next_attempt_at is None


# ---------------------------------------------------------------------------
# Required scenario: 503 -> 503 -> 200 (as an explicit mixed-code sequence,
# distinct from test_attempt_count_climbs_correctly_across_multiple_failures'
# constant-failure case)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_503_503_200_full_recovery_e2e(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    for status_code in (503, 503):
        mock_client = _mock_client(status_code)
        job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
        await mock_client.aclose()
        assert job.status == DeliveryJobStatus.RETRYING.value
        await _requeue(db_session, job_id)

    mock_client = _mock_client(200)
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert job.status == DeliveryJobStatus.SUCCESS.value
    assert job.attempt_number == 3
    await db_session.refresh(job, attribute_names=["attempts"])
    assert [a.http_status for a in job.attempts] == [503, 503, 200]


# ---------------------------------------------------------------------------
# Required scenario: timeout, then a successful retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_then_successful_retry_e2e(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    timeout_client = _mock_client(exc=httpx.TimeoutException("timed out", request=httpx.Request("POST", "https://example.com/hook")))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=timeout_client)
    await timeout_client.aclose()
    assert job.status == DeliveryJobStatus.RETRYING.value
    assert job.attempts[0].error_category == "timeout"
    await _requeue(db_session, job_id)

    success_client = _mock_client(200)
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=success_client)
    await success_client.aclose()

    assert job.status == DeliveryJobStatus.SUCCESS.value
    assert job.attempt_number == 2
    await db_session.refresh(job, attribute_names=["attempts"])
    assert job.attempts[0].error_category == "timeout"
    assert job.attempts[1].http_status == 200


# ---------------------------------------------------------------------------
# Required scenario: connection failure, then a successful retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_error_then_successful_retry_e2e(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    conn_err_client = _mock_client(exc=httpx.ConnectError("connection refused", request=httpx.Request("POST", "https://example.com/hook")))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=conn_err_client)
    await conn_err_client.aclose()
    assert job.status == DeliveryJobStatus.RETRYING.value
    assert job.attempts[0].error_category == "connection_error"
    await _requeue(db_session, job_id)

    success_client = _mock_client(200)
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=success_client)
    await success_client.aclose()

    assert job.status == DeliveryJobStatus.SUCCESS.value
    assert job.attempt_number == 2


# ---------------------------------------------------------------------------
# DLQ replay + attempt ordering: regression test for the fix in this PR
# (DeliveryJob.attempts is now ordered by started_at, not attempt_number,
# because attempt_number resets to 0 on every replay)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dlq_replay_preserves_full_attempt_history_in_chronological_order(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)
    await client.patch(
        f"/v1/endpoints/{endpoint_id}", json={"max_retry_attempts": 1}, headers={"Authorization": f"Bearer {token}"}
    )
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    # Exhaust the (tiny) retry budget -> DEAD_LETTER. attempt_number reaches 1.
    fail_client = _mock_client(503)
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=fail_client)
    await fail_client.aclose()
    assert job.status == DeliveryJobStatus.DEAD_LETTER.value
    assert job.attempt_number == 1

    # Manual replay from the DLQ.
    retry_resp = await client.post(f"/v1/dlq/{job_id}/retry", headers={"Authorization": f"Bearer {token}"})
    assert retry_resp.status_code == 200

    job_row = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
    assert job_row.attempt_number == 0  # confirmed reset, per dlq/service.py's retry_dead_letter_job

    # Post-replay attempt: attempt_number goes back to 1 -- the SAME value the
    # pre-replay attempt already used.
    success_client = _mock_client(200)
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=success_client)
    await success_client.aclose()
    assert job.status == DeliveryJobStatus.SUCCESS.value
    assert job.attempt_number == 1

    await db_session.refresh(job, attribute_names=["attempts"])
    # Two DeliveryAttempt rows exist, both legitimately numbered "1" -- this is
    # the exact ambiguity documented on DeliveryJob.attempts. Nothing was
    # overwritten (both rows are present) and ordering stays chronologically
    # correct because the relationship orders by started_at, not attempt_number.
    assert len(job.attempts) == 2
    assert [a.attempt_number for a in job.attempts] == [1, 1]
    assert [a.http_status for a in job.attempts] == [503, 200], (
        "ordering must reflect real chronological order (pre-replay failure, then "
        "post-replay success) even though both rows share attempt_number=1"
    )
    assert job.attempts[0].started_at < job.attempts[1].started_at


@pytest.mark.asyncio
async def test_attempts_relationship_orders_by_started_at_not_attempt_number(client, unique_email, db_session):
    """
    Deterministic version of the test above: Postgres's tie-breaking for equal
    `attempt_number` values happens to match insertion order in the simple
    replay case, which isn't a guarantee -- ORDER BY on a non-unique column has
    no defined tie-break order. This test removes that ambiguity entirely by
    directly constructing two DeliveryAttempt rows whose attempt_number and
    started_at orders *disagree*, so only one of the two possible `order_by`
    implementations can pass.
    """
    from datetime import datetime, timedelta, timezone

    from app.modules.delivery.models import DeliveryAttempt, ErrorCategory

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    job = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
    now = datetime.now(timezone.utc)

    # Deliberately contradictory: attempt_number ascending order is [numbered_1,
    # numbered_2], but started_at ascending order is the reverse [numbered_2,
    # numbered_1]. Only an order_by="started_at" implementation can produce
    # [200, 503] here; order_by="attempt_number" would produce [503, 200].
    numbered_1_but_later = DeliveryAttempt(
        delivery_job_id=job.id,
        organization_id=job.organization_id,
        attempt_number=1,
        queued_at=now,
        started_at=now + timedelta(seconds=10),
        completed_at=now + timedelta(seconds=11),
        duration_ms=1000,
        http_status=503,
        error_category=ErrorCategory.TRANSIENT_HTTP_ERROR.value,
        worker_id="test-worker",
    )
    numbered_2_but_earlier = DeliveryAttempt(
        delivery_job_id=job.id,
        organization_id=job.organization_id,
        attempt_number=2,
        queued_at=now,
        started_at=now,
        completed_at=now + timedelta(seconds=1),
        duration_ms=1000,
        http_status=200,
        error_category=ErrorCategory.NONE.value,
        worker_id="test-worker",
    )
    db_session.add_all([numbered_1_but_later, numbered_2_but_earlier])
    await db_session.commit()

    await db_session.refresh(job, attribute_names=["attempts"])
    assert [a.http_status for a in job.attempts] == [200, 503], (
        "job.attempts must come back in true chronological (started_at) order, "
        "not attempt_number order -- attempt_number is not a reliable ordering "
        "key once a job has been through a DLQ replay"
    )


# ---------------------------------------------------------------------------
# Cross-tenant isolation: no regression coverage existed for these two
# endpoints despite both queries already being tenant-scoped in the code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_tenant_cannot_view_another_orgs_delivery(client, db_session):
    token_a = await register_and_get_token(client, "phase1-tenant-a@example.com")
    await create_endpoint(client, token_a)
    api_key_a = await create_api_key(client, token_a)
    job_id = await _publish_and_get_job_id(client, api_key_a)

    token_b = await register_and_get_token(client, "phase1-tenant-b@example.com")
    resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404

    # Org A can still see its own delivery -- this isn't a broken lookup, just tenant-scoped.
    own_resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert own_resp.status_code == 200


@pytest.mark.asyncio
async def test_cross_tenant_cannot_view_or_replay_another_orgs_dlq_job(client, unique_email, db_session):
    from tests.integration.test_dlq import _create_dead_lettered_job

    token_a = await register_and_get_token(client, "phase1-dlq-tenant-a@example.com")
    job_id = await _create_dead_lettered_job(client, token_a, db_session)

    token_b = await register_and_get_token(client, "phase1-dlq-tenant-b@example.com")

    detail_resp = await client.get(f"/v1/dlq/{job_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert detail_resp.status_code == 404

    retry_resp = await client.post(f"/v1/dlq/{job_id}/retry", headers={"Authorization": f"Bearer {token_b}"})
    assert retry_resp.status_code == 404

    # Org B's DLQ listing must not include org A's job either.
    list_resp = await client.get("/v1/dlq", headers={"Authorization": f"Bearer {token_b}"})
    assert list_resp.json() == []

    # The job must be untouched -- endpoint only returns dead_letter jobs, so
    # this 200 alone confirms org A's job is still there in that state,
    # unaffected by org B's rejected calls above.
    owner_detail = await client.get(f"/v1/dlq/{job_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert owner_detail.status_code == 200
    assert owner_detail.json()["attempt_number"] >= 1
