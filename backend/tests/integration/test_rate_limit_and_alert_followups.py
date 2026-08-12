import uuid

import pytest

from tests.conftest import create_api_key, create_endpoint, register_and_get_token


@pytest.mark.asyncio
async def test_rate_limit_hour_and_day_tiers_now_come_from_plan_not_fixed_constants(client, unique_email, db_session):
    """
    Regression test for the follow-up: before this, hour/day limits were hardcoded
    (1000/10000) regardless of plan. Upgrading to Pro (which has higher tiers, per
    Phase 3l's DEFAULT_PLAN_SPECS) should change the reported header values.
    """
    from app.modules.billing import service as billing_service

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    free_resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "free1"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    assert free_resp.headers["x-ratelimit-limit-hour"] == "1000"
    assert free_resp.headers["x-ratelimit-limit-day"] == "10000"

    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = uuid.UUID(me_resp.json()["organization"]["id"])
    pro_plan = await billing_service.get_or_create_plan(db_session, "pro")
    subscription = await billing_service.get_or_create_subscription(db_session, organization_id=org_id)
    subscription.plan_id = pro_plan.id
    await db_session.commit()

    pro_resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "pro1"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    assert pro_resp.headers["x-ratelimit-limit-hour"] == "5000"
    assert pro_resp.headers["x-ratelimit-limit-day"] == "50000"


@pytest.mark.asyncio
async def test_per_key_minute_override_still_takes_priority_over_plan(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.api_keys.models import ApiKey

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key_secret = await create_api_key(client, token)

    key_row = (await db_session.execute(select(ApiKey))).scalars().first()
    key_row.rate_limit_per_minute = 7
    await db_session.commit()

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key_secret}
    )
    assert resp.headers["x-ratelimit-limit-minute"] == "7"


@pytest.mark.asyncio
async def test_rate_limit_abuse_alert_fires_after_repeated_violations(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.alerts.models import AlertEvent
    from app.modules.api_keys.models import ApiKey

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key_secret = await create_api_key(client, token)

    key_row = (await db_session.execute(select(ApiKey))).scalars().first()
    key_row.rate_limit_per_minute = 1
    await db_session.commit()

    await client.post(
        "/v1/alerts/rules",
        json={"condition_type": "rate_limit_abuse", "channel": "webhook", "channel_config": {"url": "https://x"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "ok"},
        headers={"X-RelayHub-Api-Key": api_key_secret},
    )
    for i in range(6):
        resp = await client.post(
            "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": f"blocked{i}"},
            headers={"X-RelayHub-Api-Key": api_key_secret},
        )
        assert resp.status_code == 429

    events = (
        await db_session.execute(select(AlertEvent).where(AlertEvent.condition_type == "rate_limit_abuse"))
    ).scalars().all()
    assert len(events) >= 1


@pytest.mark.asyncio
async def test_occasional_rate_limit_hit_does_not_trigger_abuse_alert(client, unique_email, db_session):
    """A single 429 is normal traffic shaping, not abuse -- must not fire below the threshold."""
    from sqlalchemy import select

    from app.modules.alerts.models import AlertEvent
    from app.modules.api_keys.models import ApiKey

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key_secret = await create_api_key(client, token)

    key_row = (await db_session.execute(select(ApiKey))).scalars().first()
    key_row.rate_limit_per_minute = 1
    await db_session.commit()

    await client.post(
        "/v1/alerts/rules",
        json={"condition_type": "rate_limit_abuse", "channel": "webhook", "channel_config": {"url": "https://x"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "ok"},
        headers={"X-RelayHub-Api-Key": api_key_secret},
    )
    single_block_resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "one-block"},
        headers={"X-RelayHub-Api-Key": api_key_secret},
    )
    assert single_block_resp.status_code == 429

    events = (
        await db_session.execute(select(AlertEvent).where(AlertEvent.condition_type == "rate_limit_abuse"))
    ).scalars().all()
    assert events == []


@pytest.mark.asyncio
async def test_queue_full_alert_fires_when_backlog_exceeds_threshold(client, unique_email, db_session, monkeypatch):
    from sqlalchemy import select

    from app.modules.alerts.models import AlertEvent
    from app.modules.events import service as events_service

    monkeypatch.setattr(events_service, "QUEUE_FULL_THRESHOLD", 2)

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    await client.post(
        "/v1/alerts/rules",
        json={"condition_type": "queue_full", "channel": "webhook", "channel_config": {"url": "https://x"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    for i in range(3):
        resp = await client.post(
            "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": f"q{i}"},
            headers={"X-RelayHub-Api-Key": api_key},
        )
        assert resp.status_code == 201

    events = (
        await db_session.execute(select(AlertEvent).where(AlertEvent.condition_type == "queue_full"))
    ).scalars().all()
    assert len(events) >= 1


@pytest.mark.asyncio
async def test_queue_full_does_not_fire_below_threshold(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.alerts.models import AlertEvent

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    await client.post(
        "/v1/alerts/rules",
        json={"condition_type": "queue_full", "channel": "webhook", "channel_config": {"url": "https://x"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )

    events = (
        await db_session.execute(select(AlertEvent).where(AlertEvent.condition_type == "queue_full"))
    ).scalars().all()
    assert events == []
