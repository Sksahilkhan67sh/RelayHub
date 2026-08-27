"""
Phase 5B -- copilot orchestration. Same independence guarantee as
insights/ai/service.py: nothing in app/modules/delivery/ or app/modules/dlq/
imports anything from this module, and every failure mode (disabled, timeout,
rate limit, malformed output) fails safely into a canned response rather than
raising -- a chat feature must never be able to take down request handling for
anything else.
"""

from __future__ import annotations

import logging
import time
import uuid

from prometheus_client import Counter, Histogram
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.insights.ai.provider import AICompletionRequest, AIProvider, AIProviderError
from app.modules.insights.copilot.context import assemble_context
from app.modules.insights.copilot.prompt import build_copilot_prompt
from app.modules.insights.copilot.schemas import (
    CopilotChatResponse,
    CopilotChatTurn,
    CopilotCitation,
    CopilotValidationError,
    parse_and_validate,
)

logger = logging.getLogger("relayhub.insights.copilot")

COPILOT_CHAT_COUNT = Counter("relayhub_copilot_chat_total", "Copilot chat calls", labelnames=["outcome"])  # success|disabled|failed
COPILOT_CHAT_LATENCY_SECONDS = Histogram("relayhub_copilot_chat_latency_seconds", "Copilot chat latency")

_DISABLED_ANSWER = (
    "The AI copilot isn't enabled for this deployment right now. You can still see incidents, "
    "root-cause analysis, and endpoint health directly on the Insights page."
)
_UNAVAILABLE_ANSWER = (
    "I couldn't reach the AI provider just now, so I can't answer that. The underlying incident "
    "and health data is still available on the Insights page in the meantime."
)


async def handle_chat(
    db: AsyncSession,
    provider: AIProvider,
    *,
    organization_id: uuid.UUID,
    message: str,
    history: list[CopilotChatTurn],
    incident_id: uuid.UUID | None,
) -> CopilotChatResponse:
    if not settings.AI_PROVIDER_ENABLED:
        COPILOT_CHAT_COUNT.labels(outcome="disabled").inc()
        return CopilotChatResponse(answer=_DISABLED_ANSWER, citations=[], grounded=False, disclaimer=_disclaimer())

    context = await assemble_context(db, organization_id=organization_id, focus_incident_id=incident_id)

    valid_incident_ids = {str(ic.incident_id) for ic in context.incidents}
    if context.focused_incident is not None:
        valid_incident_ids.add(str(context.focused_incident.incident_id))

    system_prompt, user_prompt = build_copilot_prompt(
        context=context,
        history=[(turn.role, turn.content) for turn in history],
        message=message,
    )

    request = AICompletionRequest(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=settings.AI_PROVIDER_MAX_TOKENS,
        timeout_seconds=settings.AI_PROVIDER_TIMEOUT_SECONDS,
    )

    start = time.monotonic()
    try:
        raw_text = await provider.complete(request)
    except AIProviderError as exc:
        COPILOT_CHAT_LATENCY_SECONDS.observe(time.monotonic() - start)
        COPILOT_CHAT_COUNT.labels(outcome="failed").inc()
        logger.warning("Copilot AI provider failure for org %s: %s", organization_id, exc)
        return CopilotChatResponse(answer=_UNAVAILABLE_ANSWER, citations=[], grounded=False, disclaimer=_disclaimer())
    except Exception:  # noqa: BLE001 -- deliberately broad, see ai/service.py precedent
        COPILOT_CHAT_LATENCY_SECONDS.observe(time.monotonic() - start)
        COPILOT_CHAT_COUNT.labels(outcome="failed").inc()
        logger.exception("Unexpected error calling AI provider for copilot chat, org %s", organization_id)
        return CopilotChatResponse(answer=_UNAVAILABLE_ANSWER, citations=[], grounded=False, disclaimer=_disclaimer())

    COPILOT_CHAT_LATENCY_SECONDS.observe(time.monotonic() - start)

    try:
        result = parse_and_validate(raw_text)
    except CopilotValidationError as exc:
        COPILOT_CHAT_COUNT.labels(outcome="failed").inc()
        logger.warning("Copilot response failed validation for org %s: %s", organization_id, exc)
        return CopilotChatResponse(answer=_UNAVAILABLE_ANSWER, citations=[], grounded=False, disclaimer=_disclaimer())

    # Never trust the model's citation IDs at face value -- drop anything that
    # wasn't actually present in the context this request assembled (defends
    # against a hallucinated or adversarially-influenced ID being rendered as a
    # clickable link to an incident, including one the model just made up).
    citations = [
        CopilotCitation(incident_id=uuid.UUID(cid), label="Referenced incident")
        for cid in result.citations
        if cid in valid_incident_ids
    ]

    COPILOT_CHAT_COUNT.labels(outcome="success").inc()
    return CopilotChatResponse(answer=result.answer, citations=citations, grounded=True, disclaimer=_disclaimer())


def _disclaimer() -> str:
    return "AI-generated answer based on your account's own delivery data. Verify against the Insights page for anything critical."
