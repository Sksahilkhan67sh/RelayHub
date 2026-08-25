from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.rate_limiter import DAY_SECONDS, HOUR_SECONDS, MINUTE_SECONDS, RateLimiter, get_rate_limiter
from app.core.config import settings
from app.core.security import hash_api_key
from app.db.session import get_db
from app.modules.api_keys.models import ApiKey

# Abuse detection: if a single API key gets rate-limited this many times within the
# window below, that's a pattern (not just one burst) -- fires the rate_limit_abuse
# alert condition (modeled since Phase 3j, unwired until this follow-up).
ABUSE_VIOLATION_THRESHOLD = 5
ABUSE_VIOLATION_WINDOW_SECONDS = 600  # 10 minutes


async def get_api_key_context(
    x_relayhub_api_key: str | None = Header(default=None, alias="X-RelayHub-Api-Key"),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """
    Authenticates requests to the public Event Publishing API using an API key
    (as opposed to the JWT-based dashboard auth in modules/auth/dependencies.py).
    """
    if not x_relayhub_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing X-RelayHub-Api-Key header")

    key_hash = hash_api_key(x_relayhub_api_key)
    # tenant-scope: safe - this IS the API-key auth lookup; key_hash is a hash of the caller's own
    # secret, and organization_id is the OUTPUT of this lookup, not an input to filter by.
    key = (await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))).scalar_one_or_none()

    if not key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    if not key.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="API key is revoked or expired")

    key.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    return key


def require_scope(scope: str):
    async def _checker(key: ApiKey = Depends(get_api_key_context)) -> ApiKey:
        if not key.has_scope(scope):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=f"API key missing required scope '{scope}'")
        return key

    return _checker


async def enforce_api_key_rate_limit(
    response: Response,
    key: ApiKey = Depends(get_api_key_context),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """
    Per spec section 13: 100/min, 1000/hr, 10000/day defaults, now sourced from the
    org's actual Plan (Phase 3l) rather than fixed constants. The per-minute tier
    still respects ApiKey.rate_limit_per_minute (Phase 3b) as a per-key override
    that takes priority over the plan's minute value; hour/day have no per-key
    override, only the plan's values -- a key-level override finer than the plan
    only really makes sense for the tightest (minute) tier in practice.

    Any tier being exceeded blocks the request AND counts as one "violation" for
    this key; repeated violations within a window trigger the rate_limit_abuse
    alert condition (see ABUSE_VIOLATION_THRESHOLD below) -- distinguishing an
    occasional burst from an actual abuse pattern.
    """
    from app.modules.billing import service as billing_service

    subscription = await billing_service.get_subscription_with_plan(db, organization_id=key.organization_id)
    plan = subscription.plan  # type: ignore[attr-defined]

    per_minute_limit = key.rate_limit_per_minute or plan.rate_limit_per_minute or settings.DEFAULT_RATE_LIMIT_PER_MIN
    tiers = [
        ("minute", per_minute_limit, MINUTE_SECONDS),
        ("hour", plan.rate_limit_per_hour, HOUR_SECONDS),
        ("day", plan.rate_limit_per_day, DAY_SECONDS),
    ]

    results = []
    for label, limit, window in tiers:
        result = await rate_limiter.check(f"apikey:{key.id}", limit=limit, window_seconds=window)
        results.append((label, result))
        response.headers[f"X-RateLimit-Limit-{label.capitalize()}"] = str(result.limit)
        response.headers[f"X-RateLimit-Remaining-{label.capitalize()}"] = str(result.remaining)
        response.headers[f"X-RateLimit-Reset-{label.capitalize()}"] = result.reset_at.isoformat()

    blocked = next((r for _, r in results if not r.allowed), None)
    if blocked:
        await _record_violation_and_maybe_alert(db, key=key, rate_limiter=rate_limiter)

        retry_after = max(1, int((blocked.reset_at - datetime.now(timezone.utc)).total_seconds()))
        # Headers set on `response` here are lost once an HTTPException is raised --
        # the custom error-envelope handler (core/error_handlers.py) builds a fresh
        # JSONResponse and only forwards exc.headers, not whatever was set on this
        # Response object. Attach via exc.headers instead so Retry-After survives.
        response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded", headers=dict(response.headers)
        )

    return key


async def _record_violation_and_maybe_alert(db: AsyncSession, *, key: ApiKey, rate_limiter: RateLimiter) -> None:
    """
    Reuses the same sliding-window rate limiter to track violations-of-the-limit as
    its own metered quantity: each 429 increments a separate 'violations' counter,
    and once THAT counter itself exceeds ABUSE_VIOLATION_THRESHOLD within the
    window, it's a real pattern -- not just a customer's one-off traffic spike.
    """
    from app.common.notification_client import get_notification_dispatcher
    from app.modules.alerts import service as alerts_service
    from app.modules.alerts.models import AlertConditionType

    violation_result = await rate_limiter.check(
        f"violations:apikey:{key.id}", limit=ABUSE_VIOLATION_THRESHOLD, window_seconds=ABUSE_VIOLATION_WINDOW_SECONDS
    )
    if violation_result.allowed:
        return  # under the abuse threshold -- just a normal rate-limit block, not a pattern yet

    await alerts_service.trigger_alert(
        db,
        organization_id=key.organization_id,
        condition_type=AlertConditionType.RATE_LIMIT_ABUSE.value,
        message=f"API key '{key.name}' has been rate-limited {ABUSE_VIOLATION_THRESHOLD}+ times in the last "
        f"{ABUSE_VIOLATION_WINDOW_SECONDS // 60} minutes -- this may indicate misconfigured client retry logic "
        f"or abuse.",
        resource_id=str(key.id),
        metadata={"api_key_id": str(key.id)},
        notification_dispatcher=get_notification_dispatcher(),
    )
