import pytest

from tests.conftest import register_and_get_token


def _extract_invite_token(sent_message: str) -> str:
    return sent_message.split("token=")[1].split()[0].strip()


@pytest.mark.asyncio
async def test_create_invitation_sends_email(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"invitee-{unique_email}"

    resp = await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == invitee_email
    assert body["role"] == "member"
    assert body["status"] == "pending"

    assert len(client.fake_notifications.sent) == 1
    sent = client.fake_notifications.sent[0]
    assert sent["config"]["to_address"] == invitee_email
    assert "accept-invitation?token=" in sent["message"]


@pytest.mark.asyncio
async def test_create_invitation_requires_admin(client, unique_email):
    resp = await client.post("/v1/org/invitations", json={"email": "x@example.com", "role": "member"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_invitation_for_existing_member_returns_409(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    other_email = f"member-{unique_email}"
    await register_and_get_token(client, other_email)
    await client.post(
        "/v1/org/members", json={"email": other_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )

    resp = await client.post(
        "/v1/org/invitations", json={"email": other_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_duplicate_pending_invitation_returns_409(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"dup-{unique_email}"

    first = await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert first.status_code == 201

    second = await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_get_invitation_by_token(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"view-{unique_email}"
    await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "admin"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    raw_token = _extract_invite_token(client.fake_notifications.sent[0]["message"])

    resp = await client.get(f"/v1/invitations/{raw_token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == invitee_email
    assert body["role"] == "admin"
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_get_invitation_unknown_token_404(client):
    resp = await client.get("/v1/invitations/not-a-real-token")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_accept_invitation_new_user_creates_account(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"newuser-{unique_email}"
    await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    raw_token = _extract_invite_token(client.fake_notifications.sent[0]["message"])

    resp = await client.post(
        "/v1/invitations/accept", json={"token": raw_token, "full_name": "New Invitee", "password": "StrongPass1"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body

    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me_resp.json()["user"]["email"] == invitee_email
    assert me_resp.json()["role"] == "member"

    members = (await client.get("/v1/org/members", headers={"Authorization": f"Bearer {owner_token}"})).json()
    assert any(m["email"] == invitee_email for m in members)


@pytest.mark.asyncio
async def test_accept_invitation_new_user_without_password_rejected(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"nopass-{unique_email}"
    await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    raw_token = _extract_invite_token(client.fake_notifications.sent[0]["message"])

    resp = await client.post("/v1/invitations/accept", json={"token": raw_token})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_accept_invitation_existing_user_requires_auth_as_that_user(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"existing-{unique_email}"
    invitee_token = await register_and_get_token(client, invitee_email)

    await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "admin"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    raw_token = _extract_invite_token(client.fake_notifications.sent[0]["message"])

    # No auth at all -> rejected, doesn't silently attach the membership.
    unauth_resp = await client.post("/v1/invitations/accept", json={"token": raw_token})
    assert unauth_resp.status_code == 409

    # Authenticated as the invited user -> succeeds and attaches the new org membership.
    resp = await client.post(
        "/v1/invitations/accept", json={"token": raw_token}, headers={"Authorization": f"Bearer {invitee_token}"}
    )
    assert resp.status_code == 200, resp.text

    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {resp.json()['access_token']}"})
    assert me_resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_accept_expired_invitation_rejected(client, unique_email, db_session):
    import uuid
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.core.security import generate_secure_token
    from app.modules.auth.models import Invitation, Organization

    owner_token = await register_and_get_token(client, unique_email)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
    org_id = uuid.UUID(me_resp.json()["organization"]["id"])
    owner_user_id = uuid.UUID(me_resp.json()["user"]["id"])

    raw_token, token_hash = generate_secure_token()
    org = (await db_session.execute(select(Organization).where(Organization.id == org_id))).scalar_one()
    db_session.add(
        Invitation(
            organization_id=org.id,
            email=f"expired-{unique_email}",
            role="member",
            invited_by_user_id=owner_user_id,
            hashed_token=token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    await db_session.commit()

    resp = await client.post(
        "/v1/invitations/accept", json={"token": raw_token, "full_name": "Late", "password": "StrongPass1"}
    )
    assert resp.status_code == 409
    assert "expired" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_accept_revoked_invitation_rejected(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"revoked-{unique_email}"
    create_resp = await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    invitation_id = create_resp.json()["id"]
    raw_token = _extract_invite_token(client.fake_notifications.sent[0]["message"])

    revoke_resp = await client.post(
        f"/v1/org/invitations/{invitation_id}/revoke", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "revoked"

    accept_resp = await client.post(
        "/v1/invitations/accept", json={"token": raw_token, "full_name": "Too Late", "password": "StrongPass1"}
    )
    assert accept_resp.status_code == 409
    assert "revoked" in accept_resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_revoke_invitation_requires_admin(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"perm-{unique_email}"
    create_resp = await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    invitation_id = create_resp.json()["id"]

    resp = await client.post(f"/v1/org/invitations/{invitation_id}/revoke")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_revoke_already_accepted_invitation_returns_409(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"accepted-{unique_email}"
    create_resp = await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    invitation_id = create_resp.json()["id"]
    raw_token = _extract_invite_token(client.fake_notifications.sent[0]["message"])

    accept_resp = await client.post(
        "/v1/invitations/accept", json={"token": raw_token, "full_name": "Accepted Already", "password": "StrongPass1"}
    )
    assert accept_resp.status_code == 200

    revoke_resp = await client.post(
        f"/v1/org/invitations/{invitation_id}/revoke", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert revoke_resp.status_code == 409


@pytest.mark.asyncio
async def test_list_invitations_returns_all_statuses(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)

    pending_email = f"pending-{unique_email}"
    revoked_email = f"revoked-list-{unique_email}"

    await client.post("/v1/org/invitations", json={"email": pending_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"})
    revoked_create = await client.post(
        "/v1/org/invitations", json={"email": revoked_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    await client.post(f"/v1/org/invitations/{revoked_create.json()['id']}/revoke", headers={"Authorization": f"Bearer {owner_token}"})

    all_resp = await client.get("/v1/org/invitations", headers={"Authorization": f"Bearer {owner_token}"})
    assert all_resp.status_code == 200
    emails = {inv["email"] for inv in all_resp.json()}
    assert pending_email in emails
    assert revoked_email in emails

    pending_only = await client.get("/v1/org/invitations?status=pending", headers={"Authorization": f"Bearer {owner_token}"})
    pending_emails = {inv["email"] for inv in pending_only.json()}
    assert pending_email in pending_emails
    assert revoked_email not in pending_emails


@pytest.mark.asyncio
async def test_list_invitations_requires_admin(client, unique_email):
    resp = await client.get("/v1/org/invitations")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_invitation_lifecycle_is_audited(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.audit.models import AuditLog

    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"audit-invite-{unique_email}"
    await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"}, headers={"Authorization": f"Bearer {owner_token}"}
    )
    raw_token = _extract_invite_token(client.fake_notifications.sent[0]["message"])
    await client.post(
        "/v1/invitations/accept", json={"token": raw_token, "full_name": "Audited Invitee", "password": "StrongPass1"}
    )

    actions = (await db_session.execute(select(AuditLog.action))).scalars().all()
    assert "invitation.created" in actions
    assert "invitation.accepted" in actions


@pytest.mark.asyncio
async def test_resend_invitation_reissues_token_and_resends_email(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"resend-{unique_email}"

    create_resp = await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    invitation_id = create_resp.json()["id"]
    first_token = _extract_invite_token(client.fake_notifications.sent[0]["message"])

    resend_resp = await client.post(
        f"/v1/org/invitations/{invitation_id}/resend", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resend_resp.status_code == 200, resend_resp.text
    assert resend_resp.json()["status"] == "pending"

    assert len(client.fake_notifications.sent) == 2
    second_token = _extract_invite_token(client.fake_notifications.sent[1]["message"])
    assert second_token != first_token

    # The old token must no longer work -- resend reissues, it doesn't add a second valid token.
    stale_lookup = await client.get(f"/v1/invitations/{first_token}")
    assert stale_lookup.status_code == 404

    fresh_lookup = await client.get(f"/v1/invitations/{second_token}")
    assert fresh_lookup.status_code == 200


@pytest.mark.asyncio
async def test_resend_invitation_requires_admin(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"resend-noadmin-{unique_email}"
    create_resp = await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    invitation_id = create_resp.json()["id"]

    resp = await client.post(f"/v1/org/invitations/{invitation_id}/resend")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_resend_already_accepted_invitation_returns_409(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"resend-accepted-{unique_email}"
    create_resp = await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    invitation_id = create_resp.json()["id"]
    token = _extract_invite_token(client.fake_notifications.sent[0]["message"])

    await client.post(
        "/v1/invitations/accept",
        json={"token": token, "password": "StrongPass1", "full_name": "New Member"},
    )

    resp = await client.post(
        f"/v1/org/invitations/{invitation_id}/resend", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_accepting_invitation_notifies_new_member_and_admins(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    invitee_email = f"notify-{unique_email}"
    await client.post(
        "/v1/org/invitations", json={"email": invitee_email, "role": "member"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    token = _extract_invite_token(client.fake_notifications.sent[0]["message"])

    accept_resp = await client.post(
        "/v1/invitations/accept",
        json={"token": token, "password": "StrongPass1", "full_name": "New Member"},
    )
    assert accept_resp.status_code == 200
    new_member_token = accept_resp.json()["access_token"]

    new_member_notifs = await client.get("/v1/notifications", headers={"Authorization": f"Bearer {new_member_token}"})
    assert any(n["type"] == "member.joined" for n in new_member_notifs.json())

    owner_notifs = await client.get("/v1/notifications", headers={"Authorization": f"Bearer {owner_token}"})
    assert any(n["type"] == "member.joined" for n in owner_notifs.json())


@pytest.mark.asyncio
async def test_create_invitation_succeeds_even_if_email_delivery_fails(client, unique_email):
    """Regression test: the invitation row commits before the email send is
    attempted, so a delivery failure (e.g. RESEND_API_KEY unset, or the provider
    being down) must not turn an already-successful invite into a 500 -- and
    especially must not leave it in a state where the client's natural retry then
    hits 'already pending' (409), making a genuinely successful invite look
    permanently broken."""
    owner_token = await register_and_get_token(client, unique_email)
    client.fake_notifications.fail_channels.add("email")

    resp = await client.post(
        "/v1/org/invitations", json={"email": f"invitee-{unique_email}", "role": "member"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "pending"

    list_resp = await client.get("/v1/org/invitations", headers={"Authorization": f"Bearer {owner_token}"})
    assert any(inv["email"] == f"invitee-{unique_email}" for inv in list_resp.json())


@pytest.mark.asyncio
async def test_resend_invitation_succeeds_even_if_email_delivery_fails(client, unique_email):
    owner_token = await register_and_get_token(client, unique_email)
    create_resp = await client.post(
        "/v1/org/invitations", json={"email": f"invitee-{unique_email}", "role": "member"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    invitation_id = create_resp.json()["id"]

    client.fake_notifications.fail_channels.add("email")
    resend_resp = await client.post(
        f"/v1/org/invitations/{invitation_id}/resend", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resend_resp.status_code == 200, resend_resp.text
