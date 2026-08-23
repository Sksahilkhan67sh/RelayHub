import pytest

from tests.conftest import create_api_key, create_endpoint, register_and_get_token


@pytest.mark.asyncio
async def test_event_publishing_blocks_after_minute_limit_and_returns_headers(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.api_keys.models import ApiKey

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key_secret = await create_api_key(client, token)

    key_row = (await db_session.execute(select(ApiKey))).scalars().first()
    key_row.rate_limit_per_minute = 3
    await db_session.commit()

    for i in range(3):
        resp = await client.post(
            "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": f"e{i}"},
            headers={"X-RelayHub-Api-Key": api_key_secret},
        )
        assert resp.status_code == 201, resp.text
        assert resp.headers["x-ratelimit-limit-minute"] == "3"

    blocked = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "e-blocked"},
        headers={"X-RelayHub-Api-Key": api_key_secret},
    )
    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers
    assert blocked.headers["x-ratelimit-remaining-minute"] == "0"
    assert blocked.json()["error"]["code"] == "rate_limited"


@pytest.mark.asyncio
async def test_different_api_keys_have_independent_rate_limits(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.api_keys.models import ApiKey

    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)

    secret_a = await create_api_key(client, token)
    secret_b = await create_api_key(client, token)

    keys = (await db_session.execute(select(ApiKey))).scalars().all()
    for k in keys:
        k.rate_limit_per_minute = 1
    await db_session.commit()

    resp_a1 = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "a1"},
        headers={"X-RelayHub-Api-Key": secret_a},
    )
    assert resp_a1.status_code == 201

    resp_a2 = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "a2"},
        headers={"X-RelayHub-Api-Key": secret_a},
    )
    assert resp_a2.status_code == 429

    # key B is a completely separate counter -- must still be allowed
    resp_b1 = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}, "idempotency_key": "b1"},
        headers={"X-RelayHub-Api-Key": secret_b},
    )
    assert resp_b1.status_code == 201


@pytest.mark.asyncio
async def test_default_minute_limit_applies_when_no_override_set(client, unique_email):
    """
    A fresh API key has rate_limit_per_minute=None, so it should fall back to
    settings.DEFAULT_RATE_LIMIT_PER_MIN (100) -- confirm normal usage isn't blocked
    and the header reports the default, not zero/None.
    """
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key_secret = await create_api_key(client, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key_secret}
    )
    assert resp.status_code == 201
    assert resp.headers["x-ratelimit-limit-minute"] == "100"


@pytest.mark.asyncio
async def test_login_rate_limited_after_many_attempts_from_same_ip(client):
    """
    Uses nonexistent emails so the per-account lockout (5 failures, existing feature)
    never triggers -- this isolates the IP-based limiter (10 requests / 5 min) added
    in this phase.
    """
    for i in range(10):
        resp = await client.post("/v1/auth/login", json={"email": f"nobody{i}@example.com", "password": "whatever"})
        assert resp.status_code == 401, f"attempt {i+1} should be a normal auth failure, not yet rate limited"

    blocked = await client.post("/v1/auth/login", json={"email": "nobody-final@example.com", "password": "whatever"})
    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers
    assert blocked.json()["error"]["code"] == "rate_limited"


@pytest.mark.asyncio
async def test_login_rate_limit_headers_present_on_normal_requests(client, unique_email):
    await register_and_get_token(client, unique_email)
    resp = await client.post("/v1/auth/login", json={"email": unique_email, "password": "StrongPass1"})
    assert resp.status_code == 200
    assert "x-ratelimit-limit-login" in resp.headers
    assert "x-ratelimit-remaining-login" in resp.headers
