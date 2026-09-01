"""
GET /auth/github/login and /auth/github/callback -- the redirect-based "Continue
with GitHub" flow. See auth/github_oauth.py for the token-exchange/account logic.

CSRF protection: /login sets a random `state` value as both a short-lived,
httponly, SameSite=Lax cookie and the `state` query param sent to GitHub. GitHub
echoes `state` back untouched on /callback; we require it to match the cookie
(the cookie only exists in the browser that started this flow -- an attacker
tricking a victim into visiting a forged /callback URL can't supply it). This is
the standard "double-submit cookie" pattern and needs no server-side session
storage, matching the rest of this API being otherwise stateless.

Token handoff: /callback redirects to `{FRONTEND_URL}/auth/callback#access_token=
...&refresh_token=...` -- a URL *fragment*, not a query string, so the tokens are
never sent to the server (no Referer/access-log leakage) and only ever touched by
the frontend callback page's own JS. The frontend already keeps these tokens in
localStorage for every other login path (see apps/web/lib/api-client.ts) -- this
doesn't change that tradeoff, just how the tokens get to the browser this once.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.modules.auth import github_oauth

router = APIRouter(prefix="/auth/github", tags=["auth"])

_STATE_COOKIE = "gh_oauth_state"


@router.get("/login")
async def github_login() -> RedirectResponse:
    if not github_oauth.is_configured():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="GitHub sign-in is not configured on this server")

    state = secrets.token_urlsafe(24)
    response = RedirectResponse(url=github_oauth.get_authorize_url(state=state), status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        _STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.ENV != "development",
        samesite="lax",
    )
    return response


@router.get("/callback")
async def github_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if not github_oauth.is_configured():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="GitHub sign-in is not configured on this server")

    failure_redirect = f"{settings.FRONTEND_URL}/login?{urlencode({'error': 'github_signin_failed'})}"

    cookie_state = request.cookies.get(_STATE_COOKIE)
    if error or not code or not state or not cookie_state or state != cookie_state:
        # Covers: the user denying access on GitHub (`error` present), GitHub
        # omitting `code`/`state`, the state cookie having expired/been cleared,
        # and a forged callback with a state that doesn't match this browser's
        # cookie -- all of these are "start over", not a 4xx the frontend renders.
        response = RedirectResponse(url=failure_redirect, status_code=status.HTTP_302_FOUND)
        response.delete_cookie(_STATE_COOKIE)
        return response

    async with httpx.AsyncClient(timeout=10.0) as http_client:
        identity = await github_oauth.fetch_github_identity(code=code, http_client=http_client)

    tokens = await github_oauth.login_or_create_user(
        db, identity=identity, ip_address=request.client.host if request.client else None
    )

    fragment = urlencode(
        {"access_token": tokens.access_token, "refresh_token": tokens.refresh_token, "expires_in": tokens.expires_in}
    )
    response = RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/callback#{fragment}", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(_STATE_COOKIE)
    return response
