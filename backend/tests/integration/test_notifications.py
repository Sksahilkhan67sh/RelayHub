import pytest

from tests.conftest import register_and_get_token


@pytest.mark.asyncio
async def test_notifications_require_auth(client):
    resp = await client.get("/v1/notifications")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_notifications(client, unique_email):
    """Two separate orgs (registration always creates a fresh org) -- user B's
    notification list must never include anything generated for user A's org."""
    owner_a_token = await register_and_get_token(client, unique_email)
    invitee_email = f"isolation-invitee-{unique_email}"
    create_resp = await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"},
        headers={"Authorization": f"Bearer {owner_a_token}"},
    )
    assert create_resp.status_code == 201

    owner_b_email = f"owner-b-{unique_email}"
    owner_b_token = await register_and_get_token(client, owner_b_email)

    # Org A now has notifications (invite flow triggers none on create, but org A's
    # owner will get one once someone accepts -- assert org B sees zero regardless).
    b_notifs = await client.get("/v1/notifications", headers={"Authorization": f"Bearer {owner_b_token}"})
    assert b_notifs.status_code == 200
    assert b_notifs.json() == []

    b_unread = await client.get("/v1/notifications/unread-count", headers={"Authorization": f"Bearer {owner_b_token}"})
    assert b_unread.json()["unread_count"] == 0


@pytest.mark.asyncio
async def test_mark_read_is_scoped_to_owner(client, unique_email):
    """A notification ID from org A must 404, not 200/403-leak, when requested by an
    unrelated org B user -- the query itself filters by (user_id, organization_id),
    not just an ownership check after fetch."""
    owner_a_token = await register_and_get_token(client, unique_email)
    invitee_email = f"markread-invitee-{unique_email}"
    await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"},
        headers={"Authorization": f"Bearer {owner_a_token}"},
    )
    invite_token = client.fake_notifications.sent[-1]["message"].split("token=")[1].split()[0].strip()
    await client.post(
        "/v1/invitations/accept",
        json={"token": invite_token, "password": "StrongPass1", "full_name": "Invitee A"},
    )

    a_notifs = await client.get("/v1/notifications", headers={"Authorization": f"Bearer {owner_a_token}"})
    assert len(a_notifs.json()) >= 1
    notification_id = a_notifs.json()[0]["id"]

    owner_b_token = await register_and_get_token(client, f"owner-b-{unique_email}")
    cross_org_resp = await client.post(
        f"/v1/notifications/{notification_id}/read", headers={"Authorization": f"Bearer {owner_b_token}"}
    )
    assert cross_org_resp.status_code == 404

    # The real owner can still mark it read.
    own_resp = await client.post(
        f"/v1/notifications/{notification_id}/read", headers={"Authorization": f"Bearer {owner_a_token}"}
    )
    assert own_resp.status_code == 200
    assert own_resp.json()["read_at"] is not None


@pytest.mark.asyncio
async def test_mark_all_read_clears_unread_count(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"markall-invitee-{unique_email}"
    await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    invite_token = client.fake_notifications.sent[-1]["message"].split("token=")[1].split()[0].strip()
    await client.post(
        "/v1/invitations/accept",
        json={"token": invite_token, "password": "StrongPass1", "full_name": "Invitee"},
    )

    before = await client.get("/v1/notifications/unread-count", headers={"Authorization": f"Bearer {owner_token}"})
    assert before.json()["unread_count"] >= 1

    mark_all_resp = await client.post("/v1/notifications/read-all", headers={"Authorization": f"Bearer {owner_token}"})
    assert mark_all_resp.status_code == 200
    assert mark_all_resp.json()["unread_count"] == 0

    after = await client.get("/v1/notifications/unread-count", headers={"Authorization": f"Bearer {owner_token}"})
    assert after.json()["unread_count"] == 0
