import pytest

from tests.conftest import register_and_get_token


@pytest.mark.asyncio
async def test_register_returns_tokens(client, unique_email):
    resp = await client.post(
        "/v1/auth/register",
        json={
            "email": unique_email,
            "password": "StrongPass1",
            "full_name": "Sahil Khan",
            "organization_name": "AlignCraft",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client, unique_email):
    payload = {
        "email": unique_email,
        "password": "StrongPass1",
        "full_name": "Sahil Khan",
        "organization_name": "AlignCraft",
    }
    first = await client.post("/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/v1/auth/register", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_weak_password_rejected(client, unique_email):
    resp = await client.post(
        "/v1/auth/register",
        json={
            "email": unique_email,
            "password": "weakpass",  # no uppercase, no digit
            "full_name": "Sahil Khan",
            "organization_name": "AlignCraft",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client, unique_email):
    await client.post(
        "/v1/auth/register",
        json={
            "email": unique_email,
            "password": "StrongPass1",
            "full_name": "Sahil Khan",
            "organization_name": "AlignCraft",
        },
    )
    resp = await client.post("/v1/auth/login", json={"email": unique_email, "password": "StrongPass1"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password_fails(client, unique_email):
    await client.post(
        "/v1/auth/register",
        json={
            "email": unique_email,
            "password": "StrongPass1",
            "full_name": "Sahil Khan",
            "organization_name": "AlignCraft",
        },
    )
    resp = await client.post("/v1/auth/login", json={"email": unique_email, "password": "WrongPass1"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_account_lockout_after_max_failed_attempts(client, unique_email):
    await client.post(
        "/v1/auth/register",
        json={
            "email": unique_email,
            "password": "StrongPass1",
            "full_name": "Sahil Khan",
            "organization_name": "AlignCraft",
        },
    )
    for _ in range(5):
        resp = await client.post("/v1/auth/login", json={"email": unique_email, "password": "WrongPass1"})
        assert resp.status_code == 401

    locked_resp = await client.post("/v1/auth/login", json={"email": unique_email, "password": "StrongPass1"})
    assert locked_resp.status_code == 423


@pytest.mark.asyncio
async def test_refresh_token_rotation(client, unique_email):
    reg = await client.post(
        "/v1/auth/register",
        json={
            "email": unique_email,
            "password": "StrongPass1",
            "full_name": "Sahil Khan",
            "organization_name": "AlignCraft",
        },
    )
    original_refresh = reg.json()["refresh_token"]

    resp = await client.post("/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert resp.status_code == 200
    new_refresh = resp.json()["refresh_token"]
    assert new_refresh != original_refresh


@pytest.mark.asyncio
async def test_refresh_token_reuse_detected_and_revokes_family(client, unique_email):
    reg = await client.post(
        "/v1/auth/register",
        json={
            "email": unique_email,
            "password": "StrongPass1",
            "full_name": "Sahil Khan",
            "organization_name": "AlignCraft",
        },
    )
    original_refresh = reg.json()["refresh_token"]

    # First rotation succeeds
    first_rotation = await client.post("/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert first_rotation.status_code == 200

    # Replaying the OLD (already-rotated) refresh token should be detected as reuse
    replay = await client.post("/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert replay.status_code == 401
    assert "reuse detected" in replay.json()["error"]["message"]

    # And the family should now be fully revoked -- even the newest token stops working
    new_refresh = first_rotation.json()["refresh_token"]
    after_revoke = await client.post("/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert after_revoke.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint_requires_auth(client):
    resp = await client.get("/v1/auth/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_endpoint_returns_profile(client, unique_email):
    reg = await client.post(
        "/v1/auth/register",
        json={
            "email": unique_email,
            "password": "StrongPass1",
            "full_name": "Sahil Khan",
            "organization_name": "AlignCraft",
        },
    )
    access_token = reg.json()["access_token"]
    resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == unique_email
    assert body["role"] == "owner"
    assert body["organization"]["name"] == "AlignCraft"


@pytest.mark.asyncio
async def test_me_endpoint_returns_401_not_500_for_deleted_user(client):
    """A valid, unexpired access token can still point at a user_id that no longer
    has a row (e.g. an old browser tab's token after the account was deleted).
    That's a 401 asking the client to sign in again, not an unhandled 500."""
    import uuid

    from app.core.security import create_access_token

    token = create_access_token(user_id=str(uuid.uuid4()), org_id=str(uuid.uuid4()), role="owner")

    resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint_exposes_is_platform_admin(client, unique_email, db_session):
    """
    Regression test: is_platform_admin was previously missing from /me's response
    entirely, even though the User model always had it -- the frontend has no other
    way to know whether to show admin-only UI (the JWT payload doesn't carry it either).
    """
    from sqlalchemy import select

    from app.modules.auth.models import User

    token = await register_and_get_token(client, unique_email)

    default_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert default_resp.json()["user"]["is_platform_admin"] is False

    user = (await db_session.execute(select(User).where(User.email == unique_email))).scalar_one()
    user.is_platform_admin = True
    await db_session.commit()

    admin_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert admin_resp.json()["user"]["is_platform_admin"] is True
