"""
Phase 5B -- copilot chat endpoint. Mounted under the existing
/insights/intelligence prefix (see insights/routes.py's docstring on why that
prefix exists) so it lives alongside the rest of the AI/intelligence surface
rather than creating a new top-level API area.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.rate_limiter import RateLimiter, get_rate_limiter
from app.db.session import get_db
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role
from app.modules.insights.ai.provider import AIProvider, get_ai_provider
from app.modules.insights.copilot import service
from app.modules.insights.copilot.schemas import CopilotChatRequest, CopilotChatResponse

router = APIRouter(prefix="/insights/intelligence/copilot", tags=["insights-intelligence-copilot"])

# Per-organization, not per-IP (multiple team members share a budget) -- deliberately
# tighter than most read endpoints since every call is a paid AI provider request.
COPILOT_RATE_LIMIT = 20
COPILOT_RATE_WINDOW_SECONDS = 3600  # 1 hour


async def _get_ai_provider_or_none() -> AIProvider | None:
    """The real get_ai_provider() raises when AI is disabled (see provider.py) --
    that's the correct default for the RCA background job, which should never run
    at all in that case. The copilot route needs to respond gracefully instead
    (settings.AI_PROVIDER_ENABLED is re-checked inside service.handle_chat), so
    this wrapper turns that expected raise into None rather than a 500."""
    from app.modules.insights.ai.provider import AIProviderError

    try:
        return get_ai_provider()
    except AIProviderError:
        return None


@router.post("/chat", response_model=CopilotChatResponse)
async def chat(
    payload: CopilotChatRequest,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    provider: AIProvider | None = Depends(_get_ai_provider_or_none),
):
    result = await rate_limiter.check(
        f"copilot:{auth.organization_id}", limit=COPILOT_RATE_LIMIT, window_seconds=COPILOT_RATE_WINDOW_SECONDS
    )
    response.headers["X-RateLimit-Limit-Copilot"] = str(result.limit)
    response.headers["X-RateLimit-Remaining-Copilot"] = str(result.remaining)
    if not result.allowed:
        retry_after = max(1, int((result.reset_at - datetime.now(timezone.utc)).total_seconds()))
        response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many copilot messages for this organization, please try again later",
            headers=dict(response.headers),
        )

    if provider is None:
        # AI disabled -- service.handle_chat also checks this, but we can only
        # construct a real provider instance when it's enabled, so short-circuit
        # here with the same canned response rather than passing None through.
        return await service.handle_chat(
            db, provider=_NullProvider(), organization_id=auth.organization_id,
            message=payload.message, history=payload.history, incident_id=payload.incident_id,
        )

    return await service.handle_chat(
        db, provider=provider, organization_id=auth.organization_id,
        message=payload.message, history=payload.history, incident_id=payload.incident_id,
    )


class _NullProvider:
    """Never actually called -- service.handle_chat checks
    settings.AI_PROVIDER_ENABLED before touching the provider at all and returns
    the disabled-state response first. Exists only so the type of `provider`
    passed to handle_chat is always a valid AIProvider, never None, keeping that
    function's signature simple."""

    async def complete(self, request):  # noqa: ANN001, ANN201 -- intentionally unreachable
        raise NotImplementedError("AI provider is disabled; this path should be unreachable")
