"""
Phase 6 developer experience: dashboard-originated test events
(POST /v1/events/test).

The important property under test is that this is NOT a separate or simulated
delivery path -- it must produce real delivery jobs through the same
service.publish_event the API-key route uses, so a developer's test event
exercises real signing, real retries, and the real DLQ.
"""

import uuid

import pytest

from app.modules.events.routes import TEST_EVENT_LIMIT
from tests.conftest import create_endpoint, register_and_get_token


@pytest.mark.asyncio
async def test_test_event_goes_through_the_real_delivery_pipeline(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    endpoint_id = await create_endpoint(client, token)

    resp = await client.post(
        "/v1/events/test",
        json={"event": "order.created", "payload": {"order_id": "test_123"}},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    # Real fan-out happened: a delivery job exists for the subscribed endpoint.
    assert len(body["delivery_jobs"]) == 1
    assert body["delivery_jobs"][0]["endpoint_id"] == endpoint_id
    assert body["event"] == "order.created"


@pytest.mark.asyncio
async def test_test_event_has_no_api_key_id(client, unique_email, db_session):
    """Dashboard-originated events leave api_key_id null, which is what makes
    them distinguishable from real API-key traffic after the fact."""
    from sqlalchemy import select

    from app.modules.events.models import Event

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)

    resp = await client.post(
        "/v1/events/test",
        json={"event": "order.created", "payload": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    event_id = uuid.UUID(resp.json()["id"])

    event = (await db_session.execute(select(Event).where(Event.id == event_id))).scalar_one()
    assert event.api_key_id is None


@pytest.mark.asyncio
async def test_test_event_can_target_a_specific_endpoint(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    endpoint_id = await create_endpoint(client, token)

    # An event type this endpoint does NOT subscribe to (valid per
    # EVENT_TYPE_PATTERN, which requires exactly namespace.name), but
    # explicitly targeted:
    # the existing endpoint_ids override should still deliver it.
    resp = await client.post(
        "/v1/events/test",
        json={"event": "other.unsubscribed", "payload": {}, "endpoint_ids": [endpoint_id]},
        headers=headers,
    )
    assert resp.status_code == 201
    assert len(resp.json()["delivery_jobs"]) == 1


@pytest.mark.asyncio
async def test_test_event_rejects_invalid_event_type(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/events/test",
        json={"event": "ab", "payload": {}},  # below min_length=3
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_test_event_requires_authentication(client):
    resp = await client.post("/v1/events/test", json={"event": "order.created", "payload": {}})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_test_event_cannot_target_another_orgs_endpoint(client):
    """Tenant isolation: explicitly naming another organization's endpoint must
    not deliver to it. The existing publish_event endpoint_ids filter already
    scopes by organization -- this pins that behavior for the new route too."""
    token_a = await register_and_get_token(client, "phase6-test-event-a@example.com")
    endpoint_a = await create_endpoint(client, token_a)

    token_b = await register_and_get_token(client, "phase6-test-event-b@example.com")
    resp = await client.post(
        "/v1/events/test",
        json={"event": "order.created", "payload": {}, "endpoint_ids": [endpoint_a]},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    # Org B's event must never fan out to org A's endpoint.
    assert resp.status_code in (201, 400, 404)
    if resp.status_code == 201:
        assert resp.json()["delivery_jobs"] == []


@pytest.mark.asyncio
async def test_test_event_is_rate_limited_per_organization(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    body = {"event": "order.created", "payload": {}}

    for i in range(TEST_EVENT_LIMIT):
        resp = await client.post("/v1/events/test", json=body, headers=headers)
        assert resp.status_code != 429, f"limit triggered early at request {i + 1}"

    blocked = await client.post("/v1/events/test", json=body, headers=headers)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
