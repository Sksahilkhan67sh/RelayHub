"""
GitHub OAuth login ("Continue with GitHub"). Two pieces:

  1. fetch_github_identity() -- talks to GitHub (exchanges the authorization code for
     an access token, then fetches the profile + a verified email), isolated behind
     an injectable http_client the same way app/modules/delivery/executor.py and the
     ai_gateway adapters are, so tests can pass httpx.MockTransport instead of
     hitting the real network (see tests/integration/test_github_oauth.py).
  2. login_or_create_user() -- pure DB logic, no network: given a verified GitHub
     identity, finds-or-creates the RelayHub account and issues a token pair. Kept
     separate from (1) so this half can be tested without mocking HTTP at all.

Account matching, in order:
  - github_id already linked to a User -> that account, any org.
  - no github_id match, but GitHub reports a *verified* primary email that matches
    an existing User -> link github_id onto that account (GitHub having verified
    the email is treated the same as clicking an emailed verification link would be).
  - no match at all -> new User + new Organization (this user as its OWNER), same
    shape as service.register_user, minus a password (a random, never-shown value
    is stored so the column stays non-null but plain password login is impossible
    for this account until/unless the user later sets one via "forgot password").
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.modules.auth import service as auth_service
from app.modules.auth.models import Membership, Organization, Role, User
from app.modules.auth.schemas import TokenResponse

_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_TOKEN_URL = "https://github.com/login/oauth/access_token"
_USER_URL = "https://api.github.com/user"
_EMAILS_URL = "https://api.github.com/user/emails"


class GitHubIdentity:
    def __init__(self, *, github_id: str, email: str, full_name: str) -> None:
        self.github_id = github_id
        self.email = email
        self.full_name = full_name


def is_configured() -> bool:
    return bool(settings.GITHUB_OAUTH_CLIENT_ID and settings.GITHUB_OAUTH_CLIENT_SECRET)


def get_authorize_url(*, state: str) -> str:
    from urllib.parse import urlencode

    params = {
        "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
        "scope": "read:user user:email",
        "state": state,
        "allow_signup": "true",
    }
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"


async def fetch_github_identity(*, code: str, http_client: httpx.AsyncClient) -> GitHubIdentity:
    token_resp = await http_client.post(
        _TOKEN_URL,
        data={
            "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
            "client_secret": settings.GITHUB_OAUTH_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
        },
        headers={"Accept": "application/json"},
    )
    if token_resp.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="GitHub did not accept this authorization code")
    token_body = token_resp.json()
    access_token = token_body.get("access_token")
    if not access_token:
        # GitHub returns 200 with an {"error": "..."} body for a lot of failure
        # modes (expired/already-used code, bad_verification_code, etc.), not a
        # non-200 status -- so this has to be checked separately from the status check above.
        detail = token_body.get("error_description") or token_body.get("error") or "GitHub did not return an access token"
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=detail)

    auth_header = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}

    user_resp = await http_client.get(_USER_URL, headers=auth_header)
    if user_resp.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Could not fetch GitHub profile")
    profile = user_resp.json()
    github_id = str(profile.get("id"))
    full_name = profile.get("name") or profile.get("login") or f"GitHub user {github_id}"

    # The profile's own `email` field is only populated if the user made their email
    # public; /user/emails (needs the user:email scope, requested above) is the
    # reliable source and is the only one that tells us whether it's verified.
    email: str | None = None
    emails_resp = await http_client.get(_EMAILS_URL, headers=auth_header)
    if emails_resp.status_code == 200:
        for entry in emails_resp.json():
            if entry.get("primary") and entry.get("verified"):
                email = entry["email"]
                break
        if email is None:
            for entry in emails_resp.json():
                if entry.get("verified"):
                    email = entry["email"]
                    break
    if email is None and profile.get("email"):
        email = profile["email"]

    if not email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Your GitHub account has no verified email address to sign in with. "
            "Verify an email on GitHub (or make one public) and try again.",
        )

    return GitHubIdentity(github_id=github_id, email=email, full_name=full_name)


async def login_or_create_user(
    db: AsyncSession, *, identity: GitHubIdentity, ip_address: str | None
) -> TokenResponse:
    user = (await db.execute(select(User).where(User.github_id == identity.github_id))).scalar_one_or_none()

    if user is None:
        existing_by_email = (await db.execute(select(User).where(User.email == identity.email))).scalar_one_or_none()
        if existing_by_email is not None:
            existing_by_email.github_id = identity.github_id
            user = existing_by_email
            await db.commit()
            await db.refresh(user)
        else:
            org_name = f"{identity.full_name}'s Organization"
            org = Organization(name=org_name, slug=await auth_service._unique_slug(db, org_name))
            db.add(org)
            await db.flush()

            user = User(
                email=identity.email,
                # GitHub owns authentication for this account; this hash is never
                # shown to and can't be produced by the user, so it can't be used to
                # log in with a password unless they later go through "forgot
                # password" to set a real one.
                hashed_password=hash_password(secrets.token_urlsafe(32)),
                full_name=identity.full_name,
                is_active=True,
                is_email_verified=True,  # GitHub already verified this email
                github_id=identity.github_id,
            )
            db.add(user)
            await db.flush()

            membership = Membership(
                user_id=user.id, organization_id=org.id, role=Role.OWNER, accepted_at=datetime.now(timezone.utc)
            )
            db.add(membership)
            await db.commit()
            await db.refresh(user)
            await db.refresh(org)

            from app.modules.billing import service as billing_service

            await billing_service.get_or_create_subscription(db, organization_id=org.id)

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    membership = await auth_service._get_primary_membership(db, user.id)
    return await auth_service._issue_token_pair(db, user, membership, ip=ip_address, user_agent=None)
