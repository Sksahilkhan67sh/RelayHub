import pytest

from tests.conftest import make_platform_admin, register_and_get_token


@pytest.mark.asyncio
async def test_list_members_includes_owner(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.get("/v1/org/members", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"
    assert members[0]["email"] == unique_email


@pytest.mark.asyncio
async def test_invite_nonexistent_user_returns_404(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.post(
        "/v1/org/members", json={"email": "nobody-here@example.com", "role": "member"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert "register first" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_invite_existing_user_adds_them_to_org(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)

    other_email = f"other-{unique_email}"
    await register_and_get_token(client, other_email)

    resp = await client.post(
        "/v1/org/members", json={"email": other_email, "role": "member"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "member"
    assert resp.json()["accepted_at"] is not None

    list_resp = await client.get("/v1/org/members", headers={"Authorization": f"Bearer {owner_token}"})
    assert len(list_resp.json()) == 2


@pytest.mark.asyncio
async def test_invite_already_member_returns_409(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    other_email = f"dup-{unique_email}"
    await register_and_get_token(client, other_email)

    await client.post("/v1/org/members", json={"email": other_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"})
    second_invite = await client.post(
        "/v1/org/members", json={"email": other_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert second_invite.status_code == 409


@pytest.mark.asyncio
async def test_update_member_role(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.auth.models import User

    owner_token = await register_and_get_token(client, unique_email)
    other_email = f"role-{unique_email}"
    await register_and_get_token(client, other_email)
    await client.post("/v1/org/members", json={"email": other_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"})

    other_user = (await db_session.execute(select(User).where(User.email == other_email))).scalar_one()

    resp = await client.patch(
        f"/v1/org/members/{other_user.id}", json={"role": "admin"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resp.status_code == 204

    members = (await client.get("/v1/org/members", headers={"Authorization": f"Bearer {owner_token}"})).json()
    updated = next(m for m in members if m["email"] == other_email)
    assert updated["role"] == "admin"


@pytest.mark.asyncio
async def test_cannot_demote_last_owner(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    my_user_id = me_resp.json()["user"]["id"]

    resp = await client.patch(
        f"/v1/org/members/{my_user_id}", json={"role": "member"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 409
    assert "last owner" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_cannot_remove_last_owner(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    my_user_id = me_resp.json()["user"]["id"]

    resp = await client.delete(f"/v1/org/members/{my_user_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_remove_member(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    other_email = f"remove-{unique_email}"
    other_token = await register_and_get_token(client, other_email)
    await client.post("/v1/org/members", json={"email": other_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"})

    other_me = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {other_token}"})
    other_user_id = other_me.json()["user"]["id"]

    resp = await client.delete(f"/v1/org/members/{other_user_id}", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 204

    members = (await client.get("/v1/org/members", headers={"Authorization": f"Bearer {owner_token}"})).json()
    assert len(members) == 1


@pytest.mark.asyncio
async def test_member_management_requires_admin(client, unique_email):
    resp = await client.post("/v1/org/members", json={"email": "x@example.com", "role": "member"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_update_organization_name(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.patch("/v1/org", json={"name": "New Org Name"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Org Name"

    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.json()["organization"]["name"] == "New Org Name"


@pytest.mark.asyncio
async def test_audit_logs_capture_member_invite(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    other_email = f"audit-{unique_email}"
    await register_and_get_token(client, other_email)
    await client.post("/v1/org/members", json={"email": other_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"})

    resp = await client.get("/v1/audit-logs", headers={"Authorization": f"Bearer {owner_token}"})
    assert resp.status_code == 200
    actions = [row["action"] for row in resp.json()]
    assert "user.invited" in actions


@pytest.mark.asyncio
async def test_audit_logs_require_admin_role(client, unique_email):
    resp = await client.get("/v1/audit-logs")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_audit_logs_are_org_scoped(client, unique_email):
    """A second org's audit trail must never leak into the first org's listing."""
    token_a = await register_and_get_token(client, unique_email)
    token_b = await register_and_get_token(client, f"scope-{unique_email}")

    other_email = f"target-{unique_email}"
    await register_and_get_token(client, other_email)
    await client.post("/v1/org/members", json={"email": other_email, "role": "member"}, headers={"Authorization": f"Bearer {token_a}"})

    org_b_logs = await client.get("/v1/audit-logs", headers={"Authorization": f"Bearer {token_b}"})
    assert org_b_logs.json() == []


@pytest.mark.asyncio
async def test_org_abuse_reports_visible_to_org_owner(client, unique_email, db_session):
    owner_token = await register_and_get_token(client, unique_email)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
    org_id = me_resp.json()["organization"]["id"]

    admin_token = await register_and_get_token(client, f"platform-{unique_email}")
    await make_platform_admin(client, db_session, admin_token)
    create_resp = await client.post(
        "/v1/admin/abuse-reports", json={"organization_id": org_id, "reason": "excessive rate limit violations"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 200

    list_resp = await client.get("/v1/org/abuse-reports", headers={"Authorization": f"Bearer {owner_token}"})
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["reason"] == "excessive rate limit violations"
    assert list_resp.json()[0]["status"] == "open"


@pytest.mark.asyncio
async def test_org_abuse_reports_require_admin_role(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    member_email = f"member-{unique_email}"
    await client.post(
        "/v1/org/invitations", json={"email": member_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    raw_token = client.fake_notifications.sent[0]["message"].split("token=")[1].split()[0].strip()
    accept_resp = await client.post(
        "/v1/invitations/accept", json={"token": raw_token, "full_name": "Org Member", "password": "StrongPass1"}
    )
    member_token = accept_resp.json()["access_token"]

    resp = await client.get("/v1/org/abuse-reports", headers={"Authorization": f"Bearer {member_token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_org_abuse_reports_are_org_scoped(client, unique_email, db_session):
    """A report filed against org A must never show up in org B's listing."""
    token_a = await register_and_get_token(client, unique_email)
    token_b = await register_and_get_token(client, f"scope-{unique_email}")

    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    org_a_id = me_resp.json()["organization"]["id"]

    admin_token = await register_and_get_token(client, f"platform-{unique_email}")
    await make_platform_admin(client, db_session, admin_token)
    await client.post(
        "/v1/admin/abuse-reports", json={"organization_id": org_a_id, "reason": "spam"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    org_b_reports = await client.get("/v1/org/abuse-reports", headers={"Authorization": f"Bearer {token_b}"})
    assert org_b_reports.json() == []
