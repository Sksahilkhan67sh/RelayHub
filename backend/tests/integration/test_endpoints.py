import uuid

import pytest

from tests.conftest import register_and_get_token


@pytest.mark.asyncio
async def test_create_endpoint_success(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/endpoints",
        json={
            "name": "Primary webhook",
            "url": "https://example.com/webhooks/relayhub",
            "environment": "live",
            "subscribed_event_types": ["payment.success", "payment.failed"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["url"] == "https://example.com/webhooks/relayhub"
    assert body["health_status"] == "unknown"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_reject_http_endpoint_in_production_mode(client, unique_email, monkeypatch):
    import app.core.config as config_module

    monkeypatch.setattr(config_module.settings, "ENV", "production")
    monkeypatch.setattr(config_module.settings, "ALLOW_HTTP_ENDPOINTS_IN_DEV", False)

    token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/endpoints",
        json={"name": "Insecure hook", "url": "http://example.com/hook"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert "Insecure http" in str(resp.json())


@pytest.mark.parametrize(
    "malicious_url",
    [
        "http://127.0.0.1/hook",
        "http://localhost/hook",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://10.0.0.5/internal",
        "http://192.168.1.1/router",
    ],
)
@pytest.mark.asyncio
async def test_reject_ssrf_target_urls(client, unique_email, malicious_url):
    token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/endpoints",
        json={"name": "Evil hook", "url": malicious_url},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422, f"Expected rejection for {malicious_url}, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_list_and_get_endpoint(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    create_resp = await client.post(
        "/v1/endpoints",
        json={"name": "Hook A", "url": "https://a.example.com/hook"},
        headers={"Authorization": f"Bearer {token}"},
    )
    endpoint_id = create_resp.json()["id"]

    list_resp = await client.get("/v1/endpoints", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    get_resp = await client.get(f"/v1/endpoints/{endpoint_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Hook A"


@pytest.mark.asyncio
async def test_update_endpoint(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    create_resp = await client.post(
        "/v1/endpoints",
        json={"name": "Hook B", "url": "https://b.example.com/hook"},
        headers={"Authorization": f"Bearer {token}"},
    )
    endpoint_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/v1/endpoints/{endpoint_id}",
        json={"is_active": False, "timeout_seconds": 30},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False
    assert update_resp.json()["timeout_seconds"] == 30


@pytest.mark.asyncio
async def test_update_endpoint_rejects_unsafe_url(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    create_resp = await client.post(
        "/v1/endpoints",
        json={"name": "Hook C", "url": "https://c.example.com/hook"},
        headers={"Authorization": f"Bearer {token}"},
    )
    endpoint_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/v1/endpoints/{endpoint_id}",
        json={"url": "http://169.254.169.254/steal-creds"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_resp.status_code == 422


@pytest.mark.asyncio
async def test_soft_delete_endpoint_hides_from_list(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    create_resp = await client.post(
        "/v1/endpoints",
        json={"name": "Hook D", "url": "https://d.example.com/hook"},
        headers={"Authorization": f"Bearer {token}"},
    )
    endpoint_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/v1/endpoints/{endpoint_id}", headers={"Authorization": f"Bearer {token}"})
    assert delete_resp.status_code == 204

    list_resp = await client.get("/v1/endpoints", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.json() == []

    get_resp = await client.get(f"/v1/endpoints/{endpoint_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_rotate_secret_returns_new_secret_once_with_grace_period(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    create_resp = await client.post(
        "/v1/endpoints",
        json={"name": "Hook E", "url": "https://e.example.com/hook"},
        headers={"Authorization": f"Bearer {token}"},
    )
    endpoint_id = create_resp.json()["id"]

    rotate_resp = await client.post(
        f"/v1/endpoints/{endpoint_id}/rotate-secret",
        json={"grace_period_hours": 48},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rotate_resp.status_code == 200
    body = rotate_resp.json()
    assert body["secret"].startswith("whsec_")
    # The NEW secret has no grace period (it's the fresh primary). The grace period is
    # attached to the OLD secret being phased out -- verify that directly via the DB.
    assert body["grace_period_ends_at"] is None

    from sqlalchemy import select

    from app.modules.endpoints.models import EndpointSecret

    old_secrets = (
        await db_session.execute(
            select(EndpointSecret).where(
                EndpointSecret.endpoint_id == uuid.UUID(endpoint_id), EndpointSecret.is_primary.is_(False)
            )
        )
    ).scalars().all()
    assert len(old_secrets) == 1
    assert old_secrets[0].grace_period_ends_at is not None


@pytest.mark.asyncio
async def test_endpoint_circuit_breaker_pauses_after_failure_threshold(client, unique_email, db_session):
    from app.modules.endpoints import service as endpoint_service
    from app.modules.endpoints.models import Endpoint, EndpointHealth

    token = await register_and_get_token(client, unique_email)
    create_resp = await client.post(
        "/v1/endpoints",
        json={"name": "Flaky hook", "url": "https://flaky.example.com/hook"},
        headers={"Authorization": f"Bearer {token}"},
    )
    endpoint_id = create_resp.json()["id"]

    from sqlalchemy import select

    endpoint = (
        await db_session.execute(select(Endpoint).where(Endpoint.id == uuid.UUID(endpoint_id)))
    ).scalar_one()

    for _ in range(10):
        endpoint = await endpoint_service.record_delivery_result(db_session, endpoint=endpoint, success=False)

    assert endpoint.health_status == EndpointHealth.UNHEALTHY.value
    assert endpoint.is_active is False
    assert endpoint.paused_reason == "auto-circuit-breaker"

    # a subsequent success should clear the auto-pause
    endpoint = await endpoint_service.record_delivery_result(db_session, endpoint=endpoint, success=True)
    assert endpoint.health_status == EndpointHealth.HEALTHY.value
    assert endpoint.is_active is True
    assert endpoint.paused_at is None
