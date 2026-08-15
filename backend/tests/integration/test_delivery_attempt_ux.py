"""
Tests for the Delivery Attempt UX backend contract: every field the frontend needs
to compute current_attempt / max_attempts / attempts_remaining / next_retry without
guessing or maintaining its own counter, across every job state.

Covers spec sections: BACKEND AUDIT, RETRY / EXHAUSTION STATES, IMPORTANT ATTEMPT
COUNT RULE, RETRY POLICY, DATA CONSISTENCY.
"""

import uuid

import httpx
import pytest
from sqlalchemy import select

from app.modules.delivery import executor as executor_module
from app.modules.delivery.executor import execute_delivery_job
from app.modules.delivery.models import DeliveryJob, DeliveryJobStatus
from app.modules.retry.schedule import DEFAULT_MAX_ATTEMPTS
from tests.conftest import create_api_key, create_endpoint, register_and_get_token


async def _publish_and_get_job_id(client, api_key) -> uuid.UUID:
    resp = await client.post(
        "/v1/events",
        json={"event": "payment.success", "payload": {"amount": 4200}},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["delivery_jobs"][0]["id"])


@pytest.fixture(autouse=True)
def patch_connect_time_resolution(monkeypatch):
    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve)


def _mock_client(status_code: int, **kwargs) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, **kwargs)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# 1. First attempt / default retry policy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_attempt_uses_default_max_attempts(client, unique_email, db_session):
    """No endpoint override set -> API reports the platform default (5), not a frontend-hardcoded value."""
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    mock_client = _mock_client(200)
    await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["max_attempts"] == DEFAULT_MAX_ATTEMPTS
    assert body["attempt_number"] == 1
    assert body["status"] == "success"


# ---------------------------------------------------------------------------
# 2. Second failed attempt / no off-by-one on the "completed attempts" number
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrying_after_first_failure_shows_completed_attempt_one_of_max(client, unique_email, db_session):
    """
    Per spec's off-by-one rule: after attempt 1 fails and attempt 2 is scheduled,
    attempt_number must read 1 (the completed attempt), NOT 2 (the not-yet-run one)
    and NOT 0.
    """
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    mock_client = _mock_client(503, text="unavailable")
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert job.status == DeliveryJobStatus.RETRYING.value
    assert job.attempt_number == 1  # completed attempts so far, not the upcoming one
    assert job.next_attempt_at is not None

    resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["attempt_number"] == 1
    assert body["max_attempts"] == DEFAULT_MAX_ATTEMPTS
    remaining = body["max_attempts"] - body["attempt_number"]
    assert remaining == 4
    assert body["next_attempt_at"] is not None


# ---------------------------------------------------------------------------
# 3. Multiple retries -- verify the count climbs correctly with no off-by-one
#    at any step, matching the spec's worked example (3 failed -> 2 remaining).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attempt_count_climbs_correctly_across_multiple_failures(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    for expected_attempt_number in (1, 2, 3):
        mock_client = _mock_client(503, text="unavailable")
        job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
        await mock_client.aclose()
        assert job.attempt_number == expected_attempt_number
        assert job.status == DeliveryJobStatus.RETRYING.value
        # Force it claimable again for the next iteration, same as a real retry would.
        job_row = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
        job_row.status = DeliveryJobStatus.QUEUED.value
        await db_session.commit()

    resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["attempt_number"] == 3
    assert body["max_attempts"] == 5
    assert body["max_attempts"] - body["attempt_number"] == 2  # spec's worked example exactly


# ---------------------------------------------------------------------------
# 4. Successful delivery after a prior retry -- next_attempt_at must NOT linger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_after_retry_clears_stale_next_attempt_at(client, unique_email, db_session):
    """
    Regression test for the bug found during this review: a job that fails once
    (scheduling a retry, setting next_attempt_at to a future time) and then succeeds
    on the next attempt must NOT keep showing that now-stale next_attempt_at --
    the UI must never imply another attempt is still coming after success.
    """
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    fail_client = _mock_client(503, text="unavailable")
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=fail_client)
    await fail_client.aclose()
    assert job.next_attempt_at is not None  # sanity: retry really was scheduled

    job_row = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
    job_row.status = DeliveryJobStatus.QUEUED.value
    await db_session.commit()

    success_client = _mock_client(200)
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=success_client)
    await success_client.aclose()

    assert job.status == DeliveryJobStatus.SUCCESS.value
    assert job.attempt_number == 2
    assert job.next_attempt_at is None  # must be cleared, not left stale from attempt 1

    resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["status"] == "success"
    assert body["attempt_number"] == 2
    assert body["next_attempt_at"] is None
    remaining = body["max_attempts"] - body["attempt_number"]
    assert remaining == 3  # true per spec's SUCCESS example, but next_attempt_at being null is what stops the UI from implying more retries


# ---------------------------------------------------------------------------
# 5 & 6. Maximum attempts reached -> DLQ / exhaustion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exhausting_all_attempts_reaches_dead_letter_with_no_next_retry(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    job = None
    for _ in range(DEFAULT_MAX_ATTEMPTS):
        mock_client = _mock_client(503, text="unavailable")
        job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
        await mock_client.aclose()
        if job.status == DeliveryJobStatus.DEAD_LETTER.value:
            break
        job_row = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
        job_row.status = DeliveryJobStatus.QUEUED.value
        await db_session.commit()

    assert job.status == DeliveryJobStatus.DEAD_LETTER.value
    assert job.attempt_number == DEFAULT_MAX_ATTEMPTS  # exactly max, never max+1
    assert job.next_attempt_at is None  # exhausted -- no more retries, no stale countdown

    resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["status"] == "dead_letter"
    assert body["attempt_number"] == body["max_attempts"] == DEFAULT_MAX_ATTEMPTS
    assert body["next_attempt_at"] is None

    dlq_resp = await client.get("/v1/dlq", headers={"Authorization": f"Bearer {token}"})
    assert dlq_resp.status_code == 200
    dlq_entries = dlq_resp.json()
    assert len(dlq_entries) == 1
    dlq_entry = dlq_entries[0]
    assert dlq_entry["attempt_number"] == dlq_entry["max_attempts"] == DEFAULT_MAX_ATTEMPTS
    assert dlq_entry["endpoint_id"] == endpoint_id


# ---------------------------------------------------------------------------
# 7. Permanent failure -- no retry scheduled, no future attempts implied
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_permanent_failure_schedules_no_retry(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    mock_client = _mock_client(404, text="not found")
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert job.status == DeliveryJobStatus.FAILED.value
    assert job.next_attempt_at is None  # permanent failure -- must not imply a retry is coming

    resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["status"] == "failed"
    assert body["next_attempt_at"] is None
    assert body["attempt_number"] == 1


# ---------------------------------------------------------------------------
# 8. Endpoint-specific retry policy overrides the platform default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_endpoint_specific_max_attempts_overrides_default(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/endpoints",
        json={"name": "custom retry endpoint", "url": "https://example.com/hook", "environment": "test", "max_retry_attempts": 3},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    job = None
    for _ in range(3):
        mock_client = _mock_client(503, text="unavailable")
        job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
        await mock_client.aclose()
        if job.status == DeliveryJobStatus.DEAD_LETTER.value:
            break
        job_row = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
        job_row.status = DeliveryJobStatus.QUEUED.value
        await db_session.commit()

    assert job.status == DeliveryJobStatus.DEAD_LETTER.value
    assert job.attempt_number == 3  # exhausted at the endpoint's override, not the platform default of 5

    resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["max_attempts"] == 3  # API reflects the real per-endpoint policy, not a hardcoded 5
    assert body["attempt_number"] == 3


# ---------------------------------------------------------------------------
# 11 & 12. Delivery list (Logs API) and Delivery Detail both expose max_attempts
#          and agree with each other for the same job.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logs_list_and_delivery_detail_agree_on_attempt_state(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    mock_client = _mock_client(503, text="unavailable")
    await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    detail_resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token}"})
    detail = detail_resp.json()

    logs_resp = await client.get("/v1/logs?limit=50", headers={"Authorization": f"Bearer {token}"})
    logs_entries = logs_resp.json()
    matching = next(e for e in logs_entries if e["id"] == str(job_id))

    assert matching["status"] == detail["status"]
    assert matching["attempt_number"] == detail["attempt_number"]
    assert matching["max_attempts"] == detail["max_attempts"]
    assert matching["next_attempt_at"] == detail["next_attempt_at"]


# ---------------------------------------------------------------------------
# 9 & 10. Attempts-remaining derivation never goes negative or over max, across
#          every terminal and non-terminal state -- exercised end-to-end.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attempts_remaining_never_negative_or_over_max_across_states(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    job_id = await _publish_and_get_job_id(client, api_key)

    for _ in range(DEFAULT_MAX_ATTEMPTS):
        resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token}"})
        body = resp.json()
        remaining = body["max_attempts"] - body["attempt_number"]
        assert 0 <= remaining <= body["max_attempts"], f"attempts_remaining={remaining} out of bounds for {body}"
        assert body["attempt_number"] <= body["max_attempts"], "attempt_number must never exceed max_attempts"

        if body["status"] in ("success", "failed", "dead_letter"):
            break

        mock_client = _mock_client(503, text="unavailable")
        await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
        await mock_client.aclose()
        job_row = (await db_session.execute(select(DeliveryJob).where(DeliveryJob.id == job_id))).scalar_one()
        if job_row.status == DeliveryJobStatus.RETRYING.value:
            job_row.status = DeliveryJobStatus.QUEUED.value
            await db_session.commit()

    # Final state check
    resp = await client.get(f"/v1/deliveries/{job_id}", headers={"Authorization": f"Bearer {token}"})
    body = resp.json()
    assert body["status"] == "dead_letter"
    assert body["attempt_number"] == body["max_attempts"]
