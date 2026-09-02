import uuid

import httpx
import pytest

from app.common.notification_client import InMemoryNotificationDispatcher, NotificationDeliveryError
from app.modules.alerts import service as alerts_service
from app.modules.alerts.models import AlertConditionType
from app.modules.delivery import executor as executor_module
from app.modules.delivery.executor import execute_delivery_job
from tests.conftest import create_api_key, create_endpoint, register_and_get_token


@pytest.fixture(autouse=True)
def patch_connect_time_resolution(monkeypatch):
    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve)


def _always_503(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503, text="down")


@pytest.mark.asyncio
async def test_create_and_list_alert_rule(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/alerts/rules",
        json={
            "condition_type": "endpoint_down",
            "severity": "critical",
            "channel": "slack",
            "channel_config": {"webhook_url": "https://hooks.slack.example.com/xyz"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["condition_type"] == "endpoint_down"
    assert body["is_enabled"] is True

    list_resp = await client.get("/v1/alerts/rules", headers={"Authorization": f"Bearer {token}"})
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_update_and_delete_alert_rule(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    create_resp = await client.post(
        "/v1/alerts/rules",
        json={"condition_type": "high_latency", "channel": "webhook", "channel_config": {"url": "https://example.com/hook"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    rule_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/v1/alerts/rules/{rule_id}", json={"is_enabled": False}, headers={"Authorization": f"Bearer {token}"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_enabled"] is False

    delete_resp = await client.delete(f"/v1/alerts/rules/{rule_id}", headers={"Authorization": f"Bearer {token}"})
    assert delete_resp.status_code == 204

    list_resp = await client.get("/v1/alerts/rules", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_trigger_alert_noop_when_no_rule_configured(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)

    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = uuid.UUID(me_resp.json()["organization"]["id"])

    dispatcher = InMemoryNotificationDispatcher()
    result = await alerts_service.trigger_alert(
        db_session,
        organization_id=org_id,
        condition_type=AlertConditionType.HIGH_LATENCY.value,
        message="should not send",
        notification_dispatcher=dispatcher,
    )
    assert result is None
    assert dispatcher.sent == []


@pytest.mark.asyncio
async def test_trigger_alert_sends_and_records_history(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = uuid.UUID(me_resp.json()["organization"]["id"])

    await client.post(
        "/v1/alerts/rules",
        json={"condition_type": "high_latency", "channel": "slack", "channel_config": {"webhook_url": "https://x"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    dispatcher = InMemoryNotificationDispatcher()
    event = await alerts_service.trigger_alert(
        db_session,
        organization_id=org_id,
        condition_type=AlertConditionType.HIGH_LATENCY.value,
        message="p99 latency exceeded 5000ms",
        notification_dispatcher=dispatcher,
    )
    assert event is not None
    assert event.delivery_status == "sent"
    assert len(dispatcher.sent) == 1
    assert dispatcher.sent[0]["channel"] == "slack"

    history_resp = await client.get("/v1/alerts/history", headers={"Authorization": f"Bearer {token}"})
    assert len(history_resp.json()) == 1
    assert history_resp.json()[0]["delivery_status"] == "sent"


@pytest.mark.asyncio
async def test_trigger_alert_throttles_repeat_within_window(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = uuid.UUID(me_resp.json()["organization"]["id"])

    await client.post(
        "/v1/alerts/rules",
        json={
            "condition_type": "repeated_failures", "channel": "webhook",
            "channel_config": {"url": "https://x"}, "throttle_window_minutes": 60,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    dispatcher = InMemoryNotificationDispatcher()
    first = await alerts_service.trigger_alert(
        db_session, organization_id=org_id, condition_type="repeated_failures",
        message="first", resource_id="ep-1", notification_dispatcher=dispatcher,
    )
    second = await alerts_service.trigger_alert(
        db_session, organization_id=org_id, condition_type="repeated_failures",
        message="second", resource_id="ep-1", notification_dispatcher=dispatcher,
    )

    assert first.delivery_status == "sent"
    assert second.delivery_status == "suppressed"
    assert len(dispatcher.sent) == 1, "Second trigger within the throttle window must not actually send"

    third = await alerts_service.trigger_alert(
        db_session, organization_id=org_id, condition_type="repeated_failures",
        message="third, different resource", resource_id="ep-2", notification_dispatcher=dispatcher,
    )
    assert third.delivery_status == "sent"
    assert len(dispatcher.sent) == 2


@pytest.mark.asyncio
async def test_trigger_alert_records_failed_delivery(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = uuid.UUID(me_resp.json()["organization"]["id"])

    await client.post(
        "/v1/alerts/rules",
        json={"condition_type": "dlq_spike", "channel": "slack", "channel_config": {"webhook_url": "https://x"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    dispatcher = InMemoryNotificationDispatcher()
    dispatcher.fail_channels.add("slack")

    event = await alerts_service.trigger_alert(
        db_session, organization_id=org_id, condition_type="dlq_spike",
        message="dlq spiking", notification_dispatcher=dispatcher,
    )
    assert event.delivery_status == "failed"
    assert "Simulated failure" in event.delivery_error


@pytest.mark.asyncio
async def test_sms_channel_raises_architecture_hook_error():
    from app.common.notification_client import RealNotificationDispatcher

    dispatcher = RealNotificationDispatcher()
    with pytest.raises(NotImplementedError, match="architecture hook"):
        await dispatcher.send(channel="sms", config={}, subject="x", message="x")


@pytest.mark.asyncio
async def test_email_channel_requires_resend_api_key(monkeypatch):
    from app.common.notification_client import RealNotificationDispatcher
    from app.core.config import settings

    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    dispatcher = RealNotificationDispatcher()
    with pytest.raises(NotificationDeliveryError, match="RESEND_API_KEY"):
        await dispatcher.send(channel="email", config={"to_address": "x@example.com"}, subject="s", message="m")


@pytest.mark.asyncio
async def test_email_channel_requires_to_address(monkeypatch):
    from app.common.notification_client import RealNotificationDispatcher
    from app.core.config import settings

    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")
    dispatcher = RealNotificationDispatcher()
    with pytest.raises(NotificationDeliveryError, match="to_address"):
        await dispatcher.send(channel="email", config={}, subject="s", message="m")


@pytest.mark.asyncio
async def test_email_channel_sends_via_resend_api(monkeypatch):
    """Regression test for the SMTP -> Resend HTTP API migration: production
    stopped sending email entirely because Render's network blocks outbound
    SMTP ports (OSError: Network is unreachable), no matter how correct the
    SMTP credentials were. This confirms the real dispatcher now hits the
    documented Resend endpoint/payload shape instead."""
    from app.common.notification_client import RealNotificationDispatcher
    from app.core.config import settings

    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(settings, "EMAIL_FROM_ADDRESS", "RelayHub <alerts@relayhub.dev>")

    captured = {}

    async def fake_post(self, url, *, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return httpx.Response(200, json={"id": "fake-email-id"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    dispatcher = RealNotificationDispatcher()
    await dispatcher.send(channel="email", config={"to_address": "user@example.com"}, subject="Reset your password", message="Click here")

    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_test_key"
    assert captured["json"] == {
        "from": "RelayHub <alerts@relayhub.dev>",
        "to": ["user@example.com"],
        "subject": "Reset your password",
        "text": "Click here",
    }


@pytest.mark.asyncio
async def test_email_channel_raises_on_resend_error_response(monkeypatch):
    from app.common.notification_client import RealNotificationDispatcher
    from app.core.config import settings

    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")

    async def fake_post(self, url, *, headers=None, json=None, timeout=None):
        return httpx.Response(422, json={"message": "Invalid `to` field"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    dispatcher = RealNotificationDispatcher()
    with pytest.raises(NotificationDeliveryError, match="422"):
        await dispatcher.send(channel="email", config={"to_address": "user@example.com"}, subject="s", message="m")


@pytest.mark.asyncio
async def test_test_alert_action_bypasses_throttle_and_reports_status(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    create_resp = await client.post(
        "/v1/alerts/rules",
        json={"condition_type": "billing_threshold", "channel": "slack", "channel_config": {"webhook_url": "https://x"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    rule_id = create_resp.json()["id"]

    resp = await client.post(f"/v1/alerts/rules/{rule_id}/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["delivery_status"] in ("sent", "failed")


@pytest.mark.asyncio
async def test_endpoint_down_alert_fires_on_circuit_breaker_pause(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.alerts.models import AlertEvent

    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    await client.post(
        "/v1/alerts/rules",
        json={"condition_type": "endpoint_down", "channel": "webhook", "channel_config": {"url": "https://x"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_always_503))
    for i in range(10):
        resp = await client.post(
            "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": f"j{i}"},
            headers={"X-RelayHub-Api-Key": api_key},
        )
        job_id = uuid.UUID(resp.json()["delivery_jobs"][0]["id"])
        await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    events = (
        await db_session.execute(select(AlertEvent).where(AlertEvent.condition_type == "endpoint_down"))
    ).scalars().all()
    assert len(events) == 1, "endpoint_down should fire exactly once at the pause transition, not on every failure"
    assert events[0].resource_id == endpoint_id


@pytest.mark.asyncio
async def test_repeated_failures_alert_fires_on_dead_letter(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.alerts.models import AlertEvent

    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)
    await client.patch(
        f"/v1/endpoints/{endpoint_id}", json={"max_retry_attempts": 0}, headers={"Authorization": f"Bearer {token}"}
    )
    api_key = await create_api_key(client, token)

    await client.post(
        "/v1/alerts/rules",
        json={"condition_type": "repeated_failures", "channel": "webhook", "channel_config": {"url": "https://x"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = uuid.UUID(resp.json()["delivery_jobs"][0]["id"])

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_always_503))
    job = await execute_delivery_job(db_session, job_id=job_id, http_client=mock_client)
    await mock_client.aclose()

    assert job.status == "dead_letter"
    events = (
        await db_session.execute(select(AlertEvent).where(AlertEvent.condition_type == "repeated_failures"))
    ).scalars().all()
    assert len(events) == 1
    assert events[0].resource_id == endpoint_id


@pytest.mark.asyncio
async def test_alerts_rules_require_admin_role(client, unique_email):
    resp = await client.post(
        "/v1/alerts/rules", json={"condition_type": "endpoint_down", "channel": "slack", "channel_config": {}}
    )
    assert resp.status_code in (401, 403)
