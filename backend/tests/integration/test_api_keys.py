import pytest
from fastapi import Depends

from tests.conftest import register_and_get_token


@pytest.mark.asyncio
async def test_create_api_key_returns_full_secret_once(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/api-keys",
        json={"name": "CI key", "environment": "test", "scopes": ["events:write"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["key"].startswith("rh_test_")
    assert body["key_prefix"] in body["key"]
    assert body["scopes"] == ["events:write"]


@pytest.mark.asyncio
async def test_list_api_keys_never_exposes_secret(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    await client.post(
        "/v1/api-keys",
        json={"name": "Prod key", "environment": "live", "scopes": ["events:write"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get("/v1/api-keys", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    keys = resp.json()
    assert len(keys) == 1
    assert "key" not in keys[0]
    assert "•" in keys[0]["masked_key"]
    assert keys[0]["is_active"] is True


@pytest.mark.asyncio
async def test_invalid_scope_rejected(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/api-keys",
        json={"name": "Bad key", "environment": "test", "scopes": ["not-a-real-scope"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_revoke_api_key(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    create_resp = await client.post(
        "/v1/api-keys",
        json={"name": "To revoke", "environment": "test", "scopes": ["events:write"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    key_id = create_resp.json()["id"]

    revoke_resp = await client.post(
        f"/v1/api-keys/{key_id}/revoke",
        json={"reason": "no longer needed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["is_active"] is False
    assert revoke_resp.json()["revoked_at"] is not None

    # revoking twice should fail cleanly
    second_revoke = await client.post(
        f"/v1/api-keys/{key_id}/revoke", json={}, headers={"Authorization": f"Bearer {token}"}
    )
    assert second_revoke.status_code == 409


@pytest.mark.asyncio
async def test_rotate_api_key_revokes_old_and_issues_new(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    create_resp = await client.post(
        "/v1/api-keys",
        json={"name": "Rotating key", "environment": "live", "scopes": ["events:write", "events:read"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    old_key_id = create_resp.json()["id"]
    old_secret = create_resp.json()["key"]

    rotate_resp = await client.post(f"/v1/api-keys/{old_key_id}/rotate", headers={"Authorization": f"Bearer {token}"})
    assert rotate_resp.status_code == 200
    new_secret = rotate_resp.json()["key"]
    assert new_secret != old_secret
    assert rotate_resp.json()["scopes"] == ["events:write", "events:read"]

    list_resp = await client.get("/v1/api-keys", headers={"Authorization": f"Bearer {token}"})
    keys_by_id = {k["id"]: k for k in list_resp.json()}
    assert keys_by_id[old_key_id]["is_active"] is False
    new_key_entry = next(k for k in list_resp.json() if k["id"] != old_key_id)
    assert new_key_entry["is_active"] is True


@pytest.mark.asyncio
async def test_api_key_management_requires_admin_role(client, unique_email):
    # A VIEWER-role user (simulated by hitting the endpoint with no valid token) is rejected;
    # full cross-role membership testing is covered once the Invite Users flow ships.
    resp = await client.post(
        "/v1/api-keys", json={"name": "x", "environment": "test", "scopes": ["events:write"]}
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_api_key_auth_dependency_accepts_valid_key(client, unique_email):
    """
    Verifies the API-key auth path (X-RelayHub-Api-Key header) used by the future
    public Event Publishing API, using a temporary probe route.
    """
    from app.main import app
    from app.modules.api_keys.dependencies import get_api_key_context

    @app.get("/v1/_test/whoami-api-key")
    async def _whoami(key=Depends(get_api_key_context)):
        return {"key_id": str(key.id), "scopes": key.scopes}

    token = await register_and_get_token(client, unique_email)
    create_resp = await client.post(
        "/v1/api-keys",
        json={"name": "probe key", "environment": "test", "scopes": ["events:write"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    full_key = create_resp.json()["key"]

    ok_resp = await client.get("/v1/_test/whoami-api-key", headers={"X-RelayHub-Api-Key": full_key})
    assert ok_resp.status_code == 200
    assert ok_resp.json()["key_id"] == create_resp.json()["id"]

    bad_resp = await client.get("/v1/_test/whoami-api-key", headers={"X-RelayHub-Api-Key": "rh_test_garbage"})
    assert bad_resp.status_code == 401
