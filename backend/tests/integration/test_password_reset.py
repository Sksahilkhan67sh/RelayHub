import pytest

from tests.conftest import register_and_get_token


@pytest.mark.asyncio
async def test_forgot_password_existing_email_sends_email(client, unique_email):
    await register_and_get_token(client, unique_email)

    resp = await client.post("/v1/auth/forgot-password", json={"email": unique_email})
    assert resp.status_code == 200
    assert "message" in resp.json()

    assert len(client.fake_notifications.sent) == 1
    sent = client.fake_notifications.sent[0]
    assert sent["channel"] == "email"
    assert sent["config"]["to_address"] == unique_email
    assert "reset-password?token=" in sent["message"]


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_same_response_no_email_sent(client, unique_email):
    resp = await client.post("/v1/auth/forgot-password", json={"email": f"nobody-{unique_email}"})
    assert resp.status_code == 200
    assert "message" in resp.json()
    # Never leaks whether the account exists: no email is sent, but the HTTP response
    # is identical in shape/status to the "account exists" case above.
    assert client.fake_notifications.sent == []


@pytest.mark.asyncio
async def test_forgot_password_existing_email_same_response_even_if_email_delivery_fails(client, unique_email):
    """Regression test: this endpoint's whole contract is responding identically
    whether or not the account exists, to prevent enumeration. The reset token
    commits before the email send is attempted -- a delivery failure must not
    turn a real, active user's request into a 500 while a nonexistent email
    stays a silent 200, which would itself be an enumeration side-channel
    through the response status."""
    await register_and_get_token(client, unique_email)
    client.fake_notifications.fail_channels.add("email")

    resp = await client.post("/v1/auth/forgot-password", json={"email": unique_email})
    assert resp.status_code == 200
    assert "message" in resp.json()


def _extract_reset_token(sent_message: str) -> str:
    return sent_message.split("token=")[1].split()[0].strip()


@pytest.mark.asyncio
async def test_reset_password_with_valid_token_succeeds(client, unique_email):
    await register_and_get_token(client, unique_email)
    await client.post("/v1/auth/forgot-password", json={"email": unique_email})
    raw_token = _extract_reset_token(client.fake_notifications.sent[0]["message"])

    reset_resp = await client.post(
        "/v1/auth/reset-password", json={"token": raw_token, "new_password": "NewStrongPass1"}
    )
    assert reset_resp.status_code == 204

    # Old password no longer works, new one does.
    old_login = await client.post("/v1/auth/login", json={"email": unique_email, "password": "StrongPass1"})
    assert old_login.status_code == 401

    new_login = await client.post("/v1/auth/login", json={"email": unique_email, "password": "NewStrongPass1"})
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_invalid_token_rejected(client):
    resp = await client.post(
        "/v1/auth/reset-password", json={"token": "not-a-real-token", "new_password": "NewStrongPass1"}
    )
    assert resp.status_code == 400
    assert "Invalid or expired" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_reset_password_token_is_one_time_use(client, unique_email):
    await register_and_get_token(client, unique_email)
    await client.post("/v1/auth/forgot-password", json={"email": unique_email})
    raw_token = _extract_reset_token(client.fake_notifications.sent[0]["message"])

    first = await client.post("/v1/auth/reset-password", json={"token": raw_token, "new_password": "NewStrongPass1"})
    assert first.status_code == 204

    second = await client.post("/v1/auth/reset-password", json={"token": raw_token, "new_password": "AnotherPass2"})
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_expired_token_rejected(client, unique_email, db_session):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.core.security import generate_secure_token
    from app.modules.auth.models import PasswordResetToken, User

    await register_and_get_token(client, unique_email)
    user = (await db_session.execute(select(User).where(User.email == unique_email))).scalar_one()

    raw_token, token_hash = generate_secure_token()
    db_session.add(
        PasswordResetToken(
            user_id=user.id,
            hashed_token=token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    await db_session.commit()

    resp = await client.post("/v1/auth/reset-password", json={"token": raw_token, "new_password": "NewStrongPass1"})
    assert resp.status_code == 400
    assert "Invalid or expired" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_reset_password_invalidates_previous_active_tokens(client, unique_email):
    await register_and_get_token(client, unique_email)

    await client.post("/v1/auth/forgot-password", json={"email": unique_email})
    first_token = _extract_reset_token(client.fake_notifications.sent[0]["message"])

    await client.post("/v1/auth/forgot-password", json={"email": unique_email})
    second_token = _extract_reset_token(client.fake_notifications.sent[1]["message"])

    # The first (superseded) token must no longer work, only the newest one.
    stale_resp = await client.post("/v1/auth/reset-password", json={"token": first_token, "new_password": "NewStrongPass1"})
    assert stale_resp.status_code == 400

    fresh_resp = await client.post("/v1/auth/reset-password", json={"token": second_token, "new_password": "NewStrongPass1"})
    assert fresh_resp.status_code == 204


@pytest.mark.asyncio
async def test_reset_password_forces_relogin_by_revoking_refresh_tokens(client, unique_email):
    register_resp = await client.post(
        "/v1/auth/register",
        json={"email": unique_email, "password": "StrongPass1", "full_name": "Sahil Khan", "organization_name": "AlignCraft"},
    )
    refresh_token = register_resp.json()["refresh_token"]

    await client.post("/v1/auth/forgot-password", json={"email": unique_email})
    raw_token = _extract_reset_token(client.fake_notifications.sent[0]["message"])
    await client.post("/v1/auth/reset-password", json={"token": raw_token, "new_password": "NewStrongPass1"})

    refresh_resp = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_weak_password_rejected(client, unique_email):
    await register_and_get_token(client, unique_email)
    await client.post("/v1/auth/forgot-password", json={"email": unique_email})
    raw_token = _extract_reset_token(client.fake_notifications.sent[0]["message"])

    resp = await client.post("/v1/auth/reset-password", json={"token": raw_token, "new_password": "weakpass"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_forgot_password_rate_limited(client, unique_email):
    for _ in range(5):
        ok = await client.post("/v1/auth/forgot-password", json={"email": unique_email})
        assert ok.status_code == 200

    limited = await client.post("/v1/auth/forgot-password", json={"email": unique_email})
    assert limited.status_code == 429


@pytest.mark.asyncio
async def test_password_reset_requests_and_completion_are_audited(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.audit.models import AuditLog

    await register_and_get_token(client, unique_email)
    await client.post("/v1/auth/forgot-password", json={"email": unique_email})
    raw_token = _extract_reset_token(client.fake_notifications.sent[0]["message"])
    await client.post("/v1/auth/reset-password", json={"token": raw_token, "new_password": "NewStrongPass1"})

    # Password-reset audit entries are org-independent (logged with organization_id=None,
    # since the request happens before any org context is resolved), so query directly.
    actions = (await db_session.execute(select(AuditLog.action))).scalars().all()
    assert "auth.password_reset_requested" in actions
    assert "auth.password_reset_completed" in actions
