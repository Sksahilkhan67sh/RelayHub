import uuid

import pytest

from tests.conftest import create_api_key, create_endpoint, register_and_get_token, upgrade_to_pro


@pytest.mark.asyncio
async def test_new_org_is_auto_provisioned_on_free_plan(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.get("/v1/billing/subscription", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"]["tier"] == "free"
    assert body["status"] == "active"


@pytest.mark.asyncio
async def test_list_plans_returns_all_four_tiers(client):
    resp = await client.get("/v1/billing/plans")
    assert resp.status_code == 200
    tiers = {p["tier"] for p in resp.json()}
    assert tiers == {"free", "starter", "pro", "enterprise"}

    free = next(p for p in resp.json() if p["tier"] == "free")
    assert free["max_deliveries_per_month"] == 1000
    assert free["max_endpoints"] == 1
    assert free["log_retention_days"] == 7

    pro = next(p for p in resp.json() if p["tier"] == "pro")
    assert pro["max_endpoints"] is None
    assert pro["has_advanced_analytics"] is True


@pytest.mark.asyncio
async def test_free_plan_blocks_second_endpoint(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)

    resp = await client.post(
        "/v1/endpoints",
        json={"name": "second", "url": "https://second.example.com/hook"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 402
    assert resp.json()["error"]["code"] == "payment_required"
    assert "Upgrade" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_upgrading_to_pro_lifts_endpoint_limit(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    await upgrade_to_pro(client, db_session, token)

    resp = await client.post(
        "/v1/endpoints",
        json={"name": "second", "url": "https://second.example.com/hook"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_free_plan_blocks_events_over_monthly_limit(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.billing import service as billing_service
    from app.modules.billing.models import Plan

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = uuid.UUID(me_resp.json()["organization"]["id"])
    subscription = await billing_service.get_or_create_subscription(db_session, organization_id=org_id)
    plan = (await db_session.execute(select(Plan).where(Plan.id == subscription.plan_id))).scalar_one()
    plan.max_deliveries_per_month = 2
    await db_session.commit()

    for i in range(2):
        resp = await client.post(
            "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": f"e{i}"},
            headers={"X-RelayHub-Api-Key": api_key},
        )
        assert resp.status_code == 201, resp.text

    blocked = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "e-over"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    assert blocked.status_code == 402
    assert blocked.json()["error"]["code"] == "payment_required"


@pytest.mark.asyncio
async def test_plan_with_overage_allowed_does_not_block(client, unique_email, db_session):
    from app.modules.billing import service as billing_service

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = uuid.UUID(me_resp.json()["organization"]["id"])

    pro_plan = await billing_service.get_or_create_plan(db_session, "pro")
    pro_plan.max_deliveries_per_month = 1
    assert pro_plan.allow_overage is True
    subscription = await billing_service.get_or_create_subscription(db_session, organization_id=org_id)
    subscription.plan_id = pro_plan.id
    await db_session.commit()

    for i in range(3):
        resp = await client.post(
            "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": f"ov{i}"},
            headers={"X-RelayHub-Api-Key": api_key},
        )
        assert resp.status_code == 201, f"overage-allowed plan should never block, attempt {i} got {resp.status_code}"


@pytest.mark.asyncio
async def test_usage_endpoint_reports_correct_counts(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    for i in range(3):
        await client.post(
            "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": f"u{i}"},
            headers={"X-RelayHub-Api-Key": api_key},
        )

    resp = await client.get("/v1/billing/usage", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["delivery_count"] == 3
    assert body["endpoint_count"] == 1
    assert body["max_deliveries_per_month"] == 1000
    assert abs(body["percent_used"] - 0.003) < 1e-6


@pytest.mark.asyncio
async def test_checkout_session_rejects_free_and_enterprise_tiers(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    for tier in ("free", "enterprise"):
        resp = await client.post(
            "/v1/billing/checkout",
            json={"tier": tier, "success_url": "https://x/success", "cancel_url": "https://x/cancel"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400, f"tier={tier} should be rejected for self-serve checkout"


@pytest.mark.asyncio
async def test_checkout_session_requires_configured_stripe_price(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/billing/checkout",
        json={"tier": "starter", "success_url": "https://x/success", "cancel_url": "https://x/cancel"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "stripe_price_id" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_checkout_session_succeeds_once_price_id_configured(client, unique_email, db_session):
    from app.modules.billing import service as billing_service

    starter = await billing_service.get_or_create_plan(db_session, "starter")
    starter.stripe_price_id = "price_test_starter_123"
    await db_session.commit()

    token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/billing/checkout",
        json={"tier": "starter", "success_url": "https://x/success", "cancel_url": "https://x/cancel"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["checkout_url"].startswith("https://checkout.stripe.example.com/")
    assert len(client.fake_stripe.created_checkout_sessions) == 1
    assert client.fake_stripe.created_checkout_sessions[0]["trial_days"] == 14


@pytest.mark.asyncio
async def test_portal_session_requires_existing_stripe_customer(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/billing/portal", json={"return_url": "https://x/account"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 400
    assert "No billing account" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_webhook_checkout_completed_upgrades_org_plan(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me_resp.json()["organization"]["id"]

    client.fake_stripe.queue_webhook_event(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_test_123",
                    "subscription": "sub_test_123",
                    "metadata": {"organization_id": org_id, "tier": "starter"},
                }
            },
        }
    )

    resp = await client.post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=fake"})
    assert resp.status_code == 204

    sub_resp = await client.get("/v1/billing/subscription", headers={"Authorization": f"Bearer {token}"})
    assert sub_resp.json()["plan"]["tier"] == "starter"


@pytest.mark.asyncio
async def test_webhook_subscription_deleted_downgrades_to_free(client, unique_email, db_session):
    from app.modules.billing import service as billing_service

    token = await register_and_get_token(client, unique_email)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = uuid.UUID(me_resp.json()["organization"]["id"])

    pro_plan = await billing_service.get_or_create_plan(db_session, "pro")
    subscription = await billing_service.get_or_create_subscription(db_session, organization_id=org_id)
    subscription.plan_id = pro_plan.id
    subscription.stripe_subscription_id = "sub_test_456"
    await db_session.commit()

    client.fake_stripe.queue_webhook_event(
        {"type": "customer.subscription.deleted", "data": {"object": {"id": "sub_test_456"}}}
    )
    resp = await client.post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=fake"})
    assert resp.status_code == 204

    sub_resp = await client.get("/v1/billing/subscription", headers={"Authorization": f"Bearer {token}"})
    assert sub_resp.json()["plan"]["tier"] == "free"
    assert sub_resp.json()["status"] == "canceled"


@pytest.mark.asyncio
async def test_webhook_payment_failed_marks_past_due_and_triggers_alert(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.alerts.models import AlertEvent
    from app.modules.billing import service as billing_service

    token = await register_and_get_token(client, unique_email)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = uuid.UUID(me_resp.json()["organization"]["id"])

    await client.post(
        "/v1/alerts/rules",
        json={"condition_type": "billing_threshold", "channel": "webhook", "channel_config": {"url": "https://x"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    subscription = await billing_service.get_or_create_subscription(db_session, organization_id=org_id)
    subscription.stripe_subscription_id = "sub_test_789"
    await db_session.commit()

    client.fake_stripe.queue_webhook_event(
        {
            "type": "invoice.payment_failed",
            "data": {"object": {"id": "in_test_1", "subscription": "sub_test_789", "amount_due": 2900, "status": "open"}},
        }
    )
    resp = await client.post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=fake"})
    assert resp.status_code == 204

    sub_resp = await client.get("/v1/billing/subscription", headers={"Authorization": f"Bearer {token}"})
    assert sub_resp.json()["status"] == "past_due"

    events = (
        await db_session.execute(select(AlertEvent).where(AlertEvent.condition_type == "billing_threshold"))
    ).scalars().all()
    assert len(events) == 1


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(client):
    client.fake_stripe.reject_signature = True
    resp = await client.post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=bad"})
    assert resp.status_code == 400
    assert "signature" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_webhook_missing_signature_header_rejected(client):
    resp = await client.post("/v1/billing/webhook", content=b"{}")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_unrecognized_event_type_is_a_noop(client):
    client.fake_stripe.queue_webhook_event({"type": "some.unhandled.event", "data": {"object": {}}})
    resp = await client.post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=fake"})
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_invoice_history_populated_from_webhook(client, unique_email, db_session):
    from app.modules.billing import service as billing_service

    token = await register_and_get_token(client, unique_email)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = uuid.UUID(me_resp.json()["organization"]["id"])

    subscription = await billing_service.get_or_create_subscription(db_session, organization_id=org_id)
    subscription.stripe_subscription_id = "sub_test_inv"
    await db_session.commit()

    client.fake_stripe.queue_webhook_event(
        {
            "type": "invoice.paid",
            "data": {"object": {"id": "in_test_paid_1", "subscription": "sub_test_inv", "amount_paid": 2900, "status": "paid"}},
        }
    )
    await client.post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=fake"})

    resp = await client.get("/v1/billing/invoices", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["amount_cents"] == 2900
    assert resp.json()[0]["status"] == "paid"


@pytest.mark.asyncio
async def test_billing_routes_require_auth(client):
    resp = await client.get("/v1/billing/subscription")
    assert resp.status_code in (401, 403)
