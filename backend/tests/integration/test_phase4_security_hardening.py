"""
Phase 4 security hardening regression tests.

Scoped to what this phase actually changed -- deliberately not duplicating
the substantial cross-tenant coverage that already exists
(tests/integration/test_reliability_phase1_e2e.py covers delivery/DLQ
cross-tenant denial; test_insights_api.py and test_copilot_api.py cover
theirs).

Covers:
  - DLQ replay/bulk-replay/export are now rate limited per organization
    (before this phase they had no limit at all, despite bulk-replay
    re-enqueueing up to 500 delivery jobs per call)
  - the limit is per-organization, not global -- one tenant exhausting its
    budget must not deny service to another
  - rate-limit headers are present and correct
"""

import uuid

import pytest

from app.modules.dlq.routes import DLQ_BULK_REPLAY_LIMIT, DLQ_EXPORT_LIMIT
from tests.conftest import register_and_get_token


@pytest.mark.asyncio
async def test_dlq_bulk_replay_is_rate_limited(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    # An empty-but-valid body: job_ids must be non-empty per BulkRetryRequest,
    # so use a random UUID that won't match anything. The point is the rate
    # limiter, which runs as a dependency before the handler body -- whether
    # the IDs resolve is irrelevant here.
    body = {"job_ids": [str(uuid.uuid4())]}

    for i in range(DLQ_BULK_REPLAY_LIMIT):
        resp = await client.post("/v1/dlq/bulk-retry", json=body, headers=headers)
        assert resp.status_code != 429, f"limit triggered early at request {i + 1}"

    blocked = await client.post("/v1/dlq/bulk-retry", json=body, headers=headers)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert int(blocked.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_dlq_rate_limit_is_per_organization_not_global(client):
    """One tenant exhausting its replay budget must not deny service to
    another -- the failure mode a global (or badly-keyed) limiter would
    introduce."""
    token_a = await register_and_get_token(client, "phase4-rl-tenant-a@example.com")
    token_b = await register_and_get_token(client, "phase4-rl-tenant-b@example.com")
    body = {"job_ids": [str(uuid.uuid4())]}

    # Exhaust org A's budget entirely.
    for _ in range(DLQ_BULK_REPLAY_LIMIT + 1):
        await client.post("/v1/dlq/bulk-retry", json=body, headers={"Authorization": f"Bearer {token_a}"})

    a_blocked = await client.post("/v1/dlq/bulk-retry", json=body, headers={"Authorization": f"Bearer {token_a}"})
    assert a_blocked.status_code == 429

    # Org B must be entirely unaffected.
    b_resp = await client.post("/v1/dlq/bulk-retry", json=body, headers={"Authorization": f"Bearer {token_b}"})
    assert b_resp.status_code != 429


@pytest.mark.asyncio
async def test_dlq_export_is_rate_limited(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(DLQ_EXPORT_LIMIT):
        resp = await client.get("/v1/dlq/export", headers=headers)
        assert resp.status_code != 429, f"limit triggered early at request {i + 1}"

    blocked = await client.get("/v1/dlq/export", headers=headers)
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_headers_present_on_allowed_request(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.get("/v1/dlq/export", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.headers["X-RateLimit-Limit-dlq-export"] == str(DLQ_EXPORT_LIMIT)
    assert int(resp.headers["X-RateLimit-Remaining-dlq-export"]) == DLQ_EXPORT_LIMIT - 1


@pytest.mark.asyncio
async def test_dlq_rate_limit_requires_authentication_first(client):
    """The rate-limit dependency resolves auth itself (via get_current_auth) --
    an unauthenticated caller must get 401, never a 429 or a 500 from the
    limiter trying to key on a missing organization."""
    resp = await client.post("/v1/dlq/bulk-retry", json={"job_ids": [str(uuid.uuid4())]})
    assert resp.status_code in (401, 403)
