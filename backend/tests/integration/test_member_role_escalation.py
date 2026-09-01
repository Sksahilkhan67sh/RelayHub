"""
Regression tests for a privilege-escalation bug: every member-management endpoint
(create invitation, direct member add, role change, member removal) only required
ADMIN, but none of them checked whether the *target* role/change involved OWNER --
so an admin (not an owner) could grant themselves or anyone else the owner role,
demote an existing owner, or remove one. Any change that grants or removes the
owner role must require the actor to already be an owner.
"""

import pytest

from tests.conftest import register_and_get_token


async def _accept_invitation(client, raw_token: str, full_name: str, password: str = "StrongPass1") -> str:
    resp = await client.post(
        "/v1/invitations/accept", json={"token": raw_token, "full_name": full_name, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _extract_invite_token(sent_message: str) -> str:
    return sent_message.split("token=")[1].split()[0].strip()


async def _make_admin(client, owner_token: str, email: str) -> tuple[str, str]:
    """Invites `email` (no existing account) into the owner's org as admin, accepts
    the invitation, and returns (admin_token, admin_user_id) -- a token that
    genuinely authenticates as ADMIN *within the owner's org*, not a fresh org of
    their own (which is what register_and_get_token would give them instead)."""
    before = len(client.fake_notifications.sent)
    create_resp = await client.post(
        "/v1/org/invitations", json={"email": email, "role": "admin"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert create_resp.status_code == 201, create_resp.text
    raw_token = _extract_invite_token(client.fake_notifications.sent[before]["message"])
    admin_token = await _accept_invitation(client, raw_token, "Org Admin")

    members = (await client.get("/v1/org/members", headers={"Authorization": f"Bearer {owner_token}"})).json()
    admin_user_id = next(m["user_id"] for m in members if m["email"] == email)
    return admin_token, admin_user_id


async def _add_second_owner(client, owner_token: str, email: str) -> str:
    """Invites `email` into the owner's org as owner (as the real owner -- this is
    the one case that's allowed) and returns their new user_id."""
    before = len(client.fake_notifications.sent)
    create_resp = await client.post(
        "/v1/org/invitations", json={"email": email, "role": "owner"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert create_resp.status_code == 201, create_resp.text
    raw_token = _extract_invite_token(client.fake_notifications.sent[before]["message"])
    await _accept_invitation(client, raw_token, "Second Owner")

    members = (await client.get("/v1/org/members", headers={"Authorization": f"Bearer {owner_token}"})).json()
    return next(m["user_id"] for m in members if m["email"] == email)


@pytest.mark.asyncio
async def test_admin_cannot_invite_someone_as_owner(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    admin_token, _ = await _make_admin(client, owner_token, f"admin-{unique_email}")

    resp = await client.post(
        "/v1/org/invitations", json={"email": f"newowner-{unique_email}", "role": "owner"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403
    assert "owner" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_owner_can_invite_someone_as_owner(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/org/invitations", json={"email": f"newowner-{unique_email}", "role": "owner"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_admin_cannot_add_member_as_owner_directly(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    admin_token, _ = await _make_admin(client, owner_token, f"admin-{unique_email}")

    third_email = f"third-{unique_email}"
    await register_and_get_token(client, third_email)

    resp = await client.post(
        "/v1/org/members", json={"email": third_email, "role": "owner"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_promote_self_to_owner(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    admin_email = f"admin-{unique_email}"
    admin_token, admin_user_id = await _make_admin(client, owner_token, admin_email)

    resp = await client.patch(
        f"/v1/org/members/{admin_user_id}", json={"role": "owner"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 403

    # Confirm the role was genuinely not changed, not just that the response was blocked.
    members = (await client.get("/v1/org/members", headers={"Authorization": f"Bearer {owner_token}"})).json()
    assert next(m for m in members if m["user_id"] == admin_user_id)["role"] == "admin"


@pytest.mark.asyncio
async def test_admin_cannot_demote_an_owner(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    admin_token, _ = await _make_admin(client, owner_token, f"admin-{unique_email}")

    # Make a second owner (as the real owner) so "last owner" protection isn't
    # what's being tested here -- specifically the owner-only guard is.
    second_owner_id = await _add_second_owner(client, owner_token, f"owner2-{unique_email}")

    resp = await client.patch(
        f"/v1/org/members/{second_owner_id}", json={"role": "member"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_demote_another_owner(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    second_owner_id = await _add_second_owner(client, owner_token, f"owner2-{unique_email}")

    resp = await client.patch(
        f"/v1/org/members/{second_owner_id}", json={"role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_admin_cannot_remove_an_owner(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    admin_token, _ = await _make_admin(client, owner_token, f"admin-{unique_email}")

    second_owner_id = await _add_second_owner(client, owner_token, f"owner2-{unique_email}")

    resp = await client.delete(
        f"/v1/org/members/{second_owner_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 403

    members = (await client.get("/v1/org/members", headers={"Authorization": f"Bearer {owner_token}"})).json()
    assert any(m["user_id"] == second_owner_id for m in members)


@pytest.mark.asyncio
async def test_owner_can_remove_an_owner(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    second_owner_id = await _add_second_owner(client, owner_token, f"owner2-{unique_email}")

    resp = await client.delete(
        f"/v1/org/members/{second_owner_id}", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resp.status_code == 204
