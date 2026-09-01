import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.auth import github_oauth
from app.modules.auth.models import Membership, Organization, Role, User
from tests.conftest import register_and_get_token


def _github_transport(*, user_id=987654, login="octocat", name="Octo Cat", email="octo@example.com", token_ok=True):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            if not token_ok:
                return httpx.Response(200, json={"error": "bad_verification_code"})
            return httpx.Response(200, json={"access_token": "gho_faketoken", "token_type": "bearer", "scope": "read:user,user:email"})
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": user_id, "login": login, "name": name, "email": None})
        if request.url.path == "/user/emails":
            return httpx.Response(200, json=[{"email": email, "primary": True, "verified": True}])
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_fetch_github_identity_returns_verified_email():
    mock_client = _github_transport(user_id=1, login="octocat", name="Octo Cat", email="octo@example.com")
    identity = await github_oauth.fetch_github_identity(code="abc123", http_client=mock_client)
    await mock_client.aclose()

    assert identity.github_id == "1"
    assert identity.email == "octo@example.com"
    assert identity.full_name == "Octo Cat"


@pytest.mark.asyncio
async def test_fetch_github_identity_falls_back_to_login_when_no_name():
    mock_client = _github_transport(user_id=2, login="octocat", name=None)
    identity = await github_oauth.fetch_github_identity(code="abc123", http_client=mock_client)
    await mock_client.aclose()

    assert identity.full_name == "octocat"


@pytest.mark.asyncio
async def test_fetch_github_identity_rejects_bad_code():
    mock_client = _github_transport(token_ok=False)
    with pytest.raises(Exception) as exc_info:
        await github_oauth.fetch_github_identity(code="bad", http_client=mock_client)
    await mock_client.aclose()
    assert "400" in str(exc_info.value) or "bad_verification_code" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_github_identity_requires_a_verified_email():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "gho_faketoken"})
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": 3, "login": "noemail", "name": "No Email", "email": None})
        if request.url.path == "/user/emails":
            return httpx.Response(200, json=[{"email": "unverified@example.com", "primary": True, "verified": False}])
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(Exception) as exc_info:
        await github_oauth.fetch_github_identity(code="abc", http_client=mock_client)
    await mock_client.aclose()
    assert "verified email" in str(exc_info.value)


@pytest.mark.asyncio
async def test_login_or_create_user_creates_new_account_and_org(db_session):
    identity = github_oauth.GitHubIdentity(github_id="42", email="new-gh-user@example.com", full_name="New GH User")
    tokens = await github_oauth.login_or_create_user(db_session, identity=identity, ip_address="1.2.3.4")

    assert tokens.access_token

    user = (await db_session.execute(select(User).where(User.email == "new-gh-user@example.com"))).scalar_one()
    assert user.github_id == "42"
    assert user.is_email_verified is True

    membership = (await db_session.execute(select(Membership).where(Membership.user_id == user.id))).scalar_one()
    assert membership.role == Role.OWNER.value

    org = (await db_session.execute(select(Organization).where(Organization.id == membership.organization_id))).scalar_one()
    assert "New GH User" in org.name


@pytest.mark.asyncio
async def test_login_or_create_user_reuses_existing_github_id(db_session):
    identity = github_oauth.GitHubIdentity(github_id="99", email="repeat@example.com", full_name="Repeat User")
    await github_oauth.login_or_create_user(db_session, identity=identity, ip_address=None)

    users_first = (await db_session.execute(select(User).where(User.github_id == "99"))).scalars().all()
    assert len(users_first) == 1

    # Second sign-in with the same github_id (email happens to differ, e.g. they
    # changed their GitHub primary email) must not create a second account.
    identity_again = github_oauth.GitHubIdentity(github_id="99", email="changed-email@example.com", full_name="Repeat User")
    await github_oauth.login_or_create_user(db_session, identity=identity_again, ip_address=None)

    users_after = (await db_session.execute(select(User).where(User.github_id == "99"))).scalars().all()
    assert len(users_after) == 1


@pytest.mark.asyncio
async def test_login_or_create_user_links_existing_email_account(client, unique_email, db_session):
    # A user who already has a password-based RelayHub account signs in with GitHub
    # using the *same, verified* email -- this should link, not duplicate.
    await register_and_get_token(client, unique_email)
    existing = (await db_session.execute(select(User).where(User.email == unique_email))).scalar_one()
    assert existing.github_id is None

    identity = github_oauth.GitHubIdentity(github_id="555", email=unique_email, full_name="Same Person")
    tokens = await github_oauth.login_or_create_user(db_session, identity=identity, ip_address=None)
    assert tokens.access_token

    await db_session.refresh(existing)
    assert existing.github_id == "555"

    all_users = (await db_session.execute(select(User).where(User.email == unique_email))).scalars().all()
    assert len(all_users) == 1


@pytest.mark.asyncio
async def test_github_login_route_404_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_ID", "")
    resp = await client.get("/v1/auth/github/login")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_github_login_route_redirects_with_state_cookie(client, monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_SECRET", "test-client-secret")

    resp = await client.get("/v1/auth/github/login")
    assert resp.status_code == 302
    assert "github.com/login/oauth/authorize" in resp.headers["location"]
    assert "client_id=test-client-id" in resp.headers["location"]
    assert "gh_oauth_state" in resp.cookies


@pytest.mark.asyncio
async def test_github_callback_rejects_mismatched_state(client, monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_SECRET", "test-client-secret")

    client.cookies.set("gh_oauth_state", "cookie-value")
    resp = await client.get("/v1/auth/github/callback", params={"code": "abc", "state": "different-value"})
    assert resp.status_code == 302
    assert "login" in resp.headers["location"]
    assert "error=github_signin_failed" in resp.headers["location"]


@pytest.mark.asyncio
async def test_github_callback_rejects_missing_cookie(client, monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_SECRET", "test-client-secret")

    resp = await client.get("/v1/auth/github/callback", params={"code": "abc", "state": "some-state"})
    assert resp.status_code == 302
    assert "error=github_signin_failed" in resp.headers["location"]


@pytest.mark.asyncio
async def test_github_callback_success_redirects_with_tokens(client, monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_SECRET", "test-client-secret")

    async def fake_fetch_identity(*, code, http_client):
        return github_oauth.GitHubIdentity(github_id="777", email="route-test@example.com", full_name="Route Test")

    monkeypatch.setattr(github_oauth, "fetch_github_identity", fake_fetch_identity)

    client.cookies.set("gh_oauth_state", "matching-state")
    resp = await client.get("/v1/auth/github/callback", params={"code": "abc", "state": "matching-state"})

    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith(f"{settings.FRONTEND_URL}/auth/callback#")
    assert "access_token=" in location
    assert "refresh_token=" in location
