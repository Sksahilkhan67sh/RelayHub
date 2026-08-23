"""
Phase 3 -- AI orchestration (sections 2, 8, 9). This is the ONLY module that
decides whether to call an AI provider at all, and it is deliberately narrow:

  raw data -> aggregation -> deterministic detection -> incident candidate -> [HERE]

AI is invoked at most once per incident-analysis job, never per delivery event or
per anomaly (section 8: "DO NOT send every delivery event to an LLM"). If AI is
disabled, unavailable, times out, rate-limits, or returns malformed output, this
module fails safely: it returns None and the deterministic RCA from rca.py (which
already exists for every incident) remains the only RCA record. Webhook ingestion,
delivery, retry, DLQ, replay, and reconciliation never depend on this module at
all -- see section 2's independence requirement, enforced structurally by the fact
that nothing in app/modules/delivery/ or app/modules/dlq/ imports anything from
insights/ai/.
"""

from __future__ import annotations

import logging
import time

from prometheus_client import Counter, Histogram

from app.core.config import settings
from app.modules.insights.aggregation import WindowMetrics
from app.modules.insights.ai.prompt import build_incident_analysis_prompt
from app.modules.insights.ai.provider import AICompletionRequest, AIProvider, AIProviderError
from app.modules.insights.ai.schemas import AIAnalysisResult, AIAnalysisValidationError, parse_and_validate
from app.modules.insights.models import Incident

logger = logging.getLogger("relayhub.insights.ai")

# In-process only -- see app/core/metrics.py's Phase 3 section for why these
# aren't DB-refreshed gauges like the rest of the insights metrics (a failed AI
# call has no durable row to re-derive a count from). Visible per-worker-process
# on that worker's own /metrics if it ever serves one; not aggregated cluster-wide
# in this pass.
AI_ANALYSIS_COUNT = Counter("relayhub_ai_analysis_total", "AI analysis calls attempted", labelnames=["outcome"])  # outcome: success|skipped|failed
AI_ANALYSIS_LATENCY_SECONDS = Histogram("relayhub_ai_analysis_latency_seconds", "AI provider call latency")
AI_TOKEN_USAGE = Counter("relayhub_ai_tokens_total", "Tokens consumed by AI analysis calls, if reported by the provider")


class AIAnalysisOutcome:
    """Result wrapper so callers (workers/insight_tasks.py) can distinguish
    'AI produced a validated result' from 'AI was skipped/failed', and record the
    right observability counters in either case, without every caller re-deriving
    that logic."""

    def __init__(
        self,
        *,
        result: AIAnalysisResult | None,
        provider: str | None,
        model: str | None,
        skipped_reason: str | None = None,
        error: str | None = None,
    ):
        self.result = result
        self.provider = provider
        self.model = model
        self.skipped_reason = skipped_reason
        self.error = error

    @property
    def succeeded(self) -> bool:
        return self.result is not None


def should_invoke_ai_for_incident(incident: Incident) -> bool:
    """Deliberately conservative gate (section 8: 'AI should only be invoked when
    useful'). Only incidents that are actually open/investigating and not already
    trivially explained get an AI pass -- a RESOLVED incident or one where the
    deterministic classification already reached UNKNOWN doesn't need one."""
    if not settings.AI_PROVIDER_ENABLED:
        return False
    return incident.status in ("open", "investigating")


async def analyze_incident(
    provider: AIProvider,
    *,
    incident: Incident,
    metrics: WindowMetrics,
    deterministic_likely_cause: str,
    deterministic_evidence: list[dict],
    sample_destination_snippets: list[str] | None = None,
) -> AIAnalysisOutcome:
    """Runs one AI analysis pass for an incident. Never raises -- every failure
    mode (disabled, timeout, rate limit, malformed output, unexpected exception)
    is caught here and returned as a non-succeeded AIAnalysisOutcome, so callers
    never need their own try/except around this."""

    if not settings.AI_PROVIDER_ENABLED:
        return AIAnalysisOutcome(result=None, provider=None, model=None, skipped_reason="ai_disabled")

    if not should_invoke_ai_for_incident(incident):
        AI_ANALYSIS_COUNT.labels(outcome="skipped").inc()
        return AIAnalysisOutcome(result=None, provider=settings.AI_PROVIDER, model=settings.AI_PROVIDER_MODEL, skipped_reason="incident_not_eligible")

    system_prompt, user_prompt = build_incident_analysis_prompt(
        incident=incident,
        metrics=metrics,
        deterministic_likely_cause=deterministic_likely_cause,
        deterministic_evidence=deterministic_evidence,
        sample_destination_snippets=sample_destination_snippets,
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
        AI_ANALYSIS_LATENCY_SECONDS.observe(time.monotonic() - start)
        AI_ANALYSIS_COUNT.labels(outcome="failed").inc()
        logger.warning("AI provider failure for incident %s: %s", incident.id, exc)
        return AIAnalysisOutcome(result=None, provider=settings.AI_PROVIDER, model=settings.AI_PROVIDER_MODEL, error=str(exc))
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: AI failures must never propagate and break incident processing
        AI_ANALYSIS_LATENCY_SECONDS.observe(time.monotonic() - start)
        AI_ANALYSIS_COUNT.labels(outcome="failed").inc()
        logger.exception("Unexpected error calling AI provider for incident %s", incident.id)
        return AIAnalysisOutcome(result=None, provider=settings.AI_PROVIDER, model=settings.AI_PROVIDER_MODEL, error=str(exc))

    AI_ANALYSIS_LATENCY_SECONDS.observe(time.monotonic() - start)

    try:
        result = parse_and_validate(raw_text)
    except AIAnalysisValidationError as exc:
        AI_ANALYSIS_COUNT.labels(outcome="failed").inc()
        logger.warning("AI response failed validation for incident %s: %s", incident.id, exc)
        return AIAnalysisOutcome(result=None, provider=settings.AI_PROVIDER, model=settings.AI_PROVIDER_MODEL, error=str(exc))

    AI_ANALYSIS_COUNT.labels(outcome="success").inc()
    return AIAnalysisOutcome(result=result, provider=settings.AI_PROVIDER, model=settings.AI_PROVIDER_MODEL)


def ai_result_to_rca_fields(outcome: AIAnalysisOutcome) -> dict:
    """Maps a succeeded AIAnalysisOutcome to RootCauseAnalysis's fields
    (source='ai'). Caller must check outcome.succeeded first."""
    assert outcome.result is not None
    r = outcome.result
    return {
        "source": "ai",
        "likely_cause": (r.likely_causes[0] if r.likely_causes else r.summary)[:500],
        "confidence_level": r.confidence_level,
        "confidence_score": r.confidence_score,
        "evidence": [e.model_dump() for e in r.evidence],
        "recommendations": r.recommendations,
        "ai_raw_output": r.model_dump(),
        "ai_provider": outcome.provider,
        "ai_model": outcome.model,
    }
