import pytest

from tests.conftest import create_api_key, create_endpoint, register_and_get_token


@pytest.mark.asyncio
async def test_publish_event_success_creates_delivery_jobs_for_matching_endpoints(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token, environment="test")  # subscribed to everything
    api_key = await create_api_key(client, token, environment="test")

    resp = await client.post(
        "/v1/events",
        json={"event": "payment.success", "payload": {"amount": 4200}, "environment": "test"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["event"] == "payment.success"
    assert len(body["delivery_jobs"]) == 1
    assert body["delivery_jobs"][0]["status"] == "queued"
    assert client.fake_queue.queued == [uuid_from(body["delivery_jobs"][0]["id"])]


def uuid_from(s: str):
    import uuid

    return uuid.UUID(s)


@pytest.mark.asyncio
async def test_publish_event_requires_api_key(client):
    resp = await client.post("/v1/events", json={"event": "payment.success", "payload": {}})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_publish_event_requires_correct_scope(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    read_only_key = await create_api_key(client, token, scopes=["events:read"])

    resp = await client.post(
        "/v1/events",
        json={"event": "payment.success", "payload": {}},
        headers={"X-RelayHub-Api-Key": read_only_key},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_invalid_event_type_format_rejected(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events",
        json={"event": "NotAValidFormat", "payload": {}},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_idempotency_key_prevents_duplicate_event_and_duplicate_jobs(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)

    payload = {"event": "order.created", "payload": {"order_id": "abc123"}, "idempotency_key": "req-001"}
    first = await client.post("/v1/events", json=payload, headers={"X-RelayHub-Api-Key": api_key})
    second = await client.post("/v1/events", json=payload, headers={"X-RelayHub-Api-Key": api_key})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    # only ONE set of delivery jobs should have been queued, not two
    assert len(client.fake_queue.queued) == 1


@pytest.mark.asyncio
async def test_endpoint_subscribed_to_specific_types_only_matches_those(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token, subscribed_event_types=["payment.success"])
    api_key = await create_api_key(client, token)

    matching = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    assert len(matching.json()["delivery_jobs"]) == 1

    non_matching = await client.post(
        "/v1/events", json={"event": "order.created", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    assert len(non_matching.json()["delivery_jobs"]) == 0


@pytest.mark.asyncio
async def test_inactive_endpoint_does_not_receive_events(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    endpoint_id = await create_endpoint(client, token)
    await client.patch(
        f"/v1/endpoints/{endpoint_id}", json={"is_active": False}, headers={"Authorization": f"Bearer {token}"}
    )
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    assert len(resp.json()["delivery_jobs"]) == 0


@pytest.mark.asyncio
async def test_environment_mismatch_does_not_match_endpoint(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token, environment="live")  # live endpoint
    api_key = await create_api_key(client, token, environment="test")  # test key

    resp = await client.post(
        "/v1/events",
        json={"event": "payment.success", "payload": {}, "environment": "test"},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    assert len(resp.json()["delivery_jobs"]) == 0


@pytest.mark.asyncio
async def test_custom_event_type_auto_registers(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.events.models import EventType

    token = await register_and_get_token(client, unique_email)
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events",
        json={"event": "myapp.custom_thing", "payload": {}},
        headers={"X-RelayHub-Api-Key": api_key},
    )
    assert resp.status_code == 201

    event_types = (await db_session.execute(select(EventType).where(EventType.name == "myapp.custom_thing"))).scalars().all()
    assert len(event_types) == 1
    assert event_types[0].is_custom is True


@pytest.mark.asyncio
async def test_get_event_requires_dashboard_auth(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    api_key = await create_api_key(client, token)

    publish_resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {"x": 1}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    event_id = publish_resp.json()["id"]

    unauthenticated = await client.get(f"/v1/events/{event_id}")
    assert unauthenticated.status_code in (401, 403)

    authenticated = await client.get(f"/v1/events/{event_id}", headers={"Authorization": f"Bearer {token}"})
    assert authenticated.status_code == 200
    assert authenticated.json()["payload"] == {"x": 1}


@pytest.mark.asyncio
async def test_response_has_request_id_header(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    assert "x-request-id" in resp.headers


@pytest.mark.asyncio
async def test_client_supplied_request_id_is_echoed_back(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    api_key = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events",
        json={"event": "payment.success", "payload": {}},
        headers={"X-RelayHub-Api-Key": api_key, "X-Request-ID": "my-custom-trace-id"},
    )
    assert resp.headers["x-request-id"] == "my-custom-trace-id"


@pytest.mark.asyncio
async def test_404_error_uses_standardized_envelope(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    import uuid

    resp = await client.get(f"/v1/events/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
    assert "request_id" in body["error"]
