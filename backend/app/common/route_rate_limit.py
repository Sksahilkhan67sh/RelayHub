"""
Reusable, organization-scoped rate limiting for authenticated operations.

Phase 4 audit finding: rate limiting existed and was well-built
(app/common/rate_limiter.py -- sliding-window-log, Redis-backed, with an
injectable in-memory implementation for tests), but was only *applied* in
three places: API-key-authenticated event ingestion
(api_keys/dependencies.py's enforce_api_key_rate_limit), auth routes
(login/password-reset), and Copilot chat. Several expensive or abusable
JWT-authenticated operations had no limit at all -- most notably DLQ replay
(`POST /dlq/{id}/retry` and especially `POST /dlq/bulk-retry`, which
re-enqueues up to 500 delivery jobs per call, with no cap on how often a
caller may do that).

This module factors out the check-and-raise block that copilot/routes.py
already implements correctly, so other routes get identical semantics
(same headers, same 429 shape, same Retry-After computation) without each
re-implementing it. It deliberately does NOT introduce a second rate
limiting system -- it's a thin dependency wrapper over the existing
RateLimiter protocol.

Key cardinality: keys are `{bucket}:{organization_id}`. The bucket is a
fixed string chosen by the call site, and organization_id is bounded by the
number of real tenants -- no user input, no URL, no event/delivery ID ever
becomes part of a rate-limit key.

Redis-outage behavior: inherited from the underlying RateLimiter. A Redis
failure raises, which surfaces as a 500 rather than silently allowing
unlimited requests -- the same fail-closed posture the pre-existing
enforce_api_key_rate_limit and copilot limits already have. That is a
deliberate tradeoff for abuse protection on these specific expensive
operations, not an accident; see docs/operations/SECURITY.md.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from fastapi import Depends, HTTPException, Response, status

from app.common.rate_limiter import RateLimiter, get_rate_limiter
from app.modules.auth.dependencies import AuthContext, get_current_auth


def org_rate_limit(bucket: str, *, limit: int, window_seconds: int) -> Callable:
    """Build a FastAPI dependency that enforces `limit` requests per
    `window_seconds` per organization for this `bucket`.

    Usage (the auth dependency stays on the route itself, since the route
    decides which role it requires -- this only handles the limiting, and
    resolves the caller's organization independently via get_current_auth):

        @router.post("/thing", ...)
        async def do_thing(
            auth: AuthContext = Depends(require_role(Role.ADMIN)),
            _rl: None = Depends(org_rate_limit("thing", limit=10, window_seconds=60)),
        ): ...
    """

    async def _dependency(
        response: Response,
        auth: AuthContext = Depends(get_current_auth),
        rate_limiter: RateLimiter = Depends(get_rate_limiter),
    ) -> None:
        result = await rate_limiter.check(
            f"{bucket}:{auth.organization_id}", limit=limit, window_seconds=window_seconds
        )
        response.headers[f"X-RateLimit-Limit-{bucket}"] = str(result.limit)
        response.headers[f"X-RateLimit-Remaining-{bucket}"] = str(result.remaining)
        if not result.allowed:
            retry_after = max(1, int((result.reset_at - datetime.now(timezone.utc)).total_seconds()))
            response.headers["Retry-After"] = str(retry_after)
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {bucket}, please try again later",
                headers=dict(response.headers),
            )

    return _dependency
