"""
AI Gateway (Step 15). The single place that:

  resolve provider -> resolve model -> validate capability -> call adapter ->
  normalize response -> (fallback on transient failure if configured) -> metrics

insights/ai/service.py and insights/copilot/service.py call this through the
insights.ai.provider shim (unchanged call sites); this module has no
knowledge of incidents, copilot context, or prompt building -- exactly the
"DO NOT implement provider-specific logic inside Copilot/RCA/Insights"
boundary this phase requires.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from prometheus_client import Counter, Histogram

from app.modules.ai_gateway.adapters.anthropic import AnthropicAdapter
from app.modules.ai_gateway.adapters.base import ProviderAdapter
from app.modules.ai_gateway.adapters.gemini import GeminiAdapter
from app.modules.ai_gateway.adapters.openai import OpenAIAdapter
from app.modules.ai_gateway.adapters.xai import XAIAdapter
from app.modules.ai_gateway.contracts import (
    AIAuthenticationError,
    AIGatewayError,
    AIGatewayRequest,
    AIGatewayResponse,
    AIInvalidRequestError,
    AIUnknownProviderError,
)
from app.modules.ai_gateway.registry import REQUIRED_CAPABILITIES, Capability, get_provider_info, validate_capabilities

logger = logging.getLogger("relayhub.ai_gateway")

# Provider-labeled metrics (Step 25), additive alongside the pre-existing
# in-process counters in insights/ai/service.py and insights/copilot/service.py
# (which stay as-is -- see PHASE_UNIVERSAL_AI_AUDIT.md, "Files to modify").
AI_GATEWAY_REQUESTS = Counter(
    "relayhub_ai_gateway_requests_total",
    "AI gateway requests by provider/model/outcome",
    labelnames=["provider", "model", "outcome"],  # outcome: success|failed|fallback_success|fallback_failed
)
AI_GATEWAY_LATENCY_SECONDS = Histogram(
    "relayhub_ai_gateway_latency_seconds", "AI gateway call latency by provider", labelnames=["provider"]
)

# Failure modes that MAY justify trying the fallback provider (Step 19):
# transient/provider-side, not a property of the request itself. Explicitly
# excludes auth errors and invalid-request errors -- "DO NOT automatically
# fallback on: invalid API key, invalid request, security rejection,
# malformed user input" -- retrying the identical request against a
# different provider would not fix either of those.
_FALLBACK_ELIGIBLE_ERRORS = (
    "AITimeoutError",
    "AIRateLimitError",
    "AIUnavailableError",
    "AIMalformedResponseError",
    "AIProviderError",
    "AICapabilityError",
)


def _adapter_error_is_fallback_eligible(exc: Exception) -> bool:
    return type(exc).__name__ in _FALLBACK_ELIGIBLE_ERRORS and not isinstance(exc, (AIAuthenticationError, AIInvalidRequestError))


_ADAPTER_CLASSES: dict[str, type] = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
    "gemini": GeminiAdapter,
    "xai": XAIAdapter,
}


def _resolve_credentials(provider: str, settings) -> tuple[str, str]:
    """Backward-compatible credential/model resolution (Step 31).

    `AI_PROVIDER_API_KEY`/`AI_PROVIDER_MODEL` are the pre-existing generic
    settings that, before this phase, only ever meant "the Anthropic key/
    model" (the only provider that existed). That meaning is preserved
    exactly: for `provider="anthropic"`, the generic settings are always the
    primary source. For any other provider, the generic settings are used
    ONLY when that provider is the configured primary (`settings.AI_PROVIDER`)
    AND no provider-specific override is set -- so `AI_PROVIDER=openai` with
    just `AI_PROVIDER_API_KEY`/`AI_PROVIDER_MODEL` set (the natural first
    thing an operator would try) works, while a provider used purely as the
    fallback always needs its own `AI_<PROVIDER>_API_KEY`/`AI_<PROVIDER>_MODEL`."""
    specific_key = getattr(settings, f"AI_{provider.upper()}_API_KEY", "")
    specific_model = getattr(settings, f"AI_{provider.upper()}_MODEL", "")

    if provider == "anthropic":
        # Exact pre-existing behavior preserved: the generic settings ARE the
        # anthropic settings (there was no other provider before this phase).
        return settings.AI_PROVIDER_API_KEY or specific_key, settings.AI_PROVIDER_MODEL or specific_model

    if provider == settings.AI_PROVIDER:
        # This provider is the configured primary: prefer its own dedicated
        # settings, but accept the generic ones too so `AI_PROVIDER=openai` +
        # `AI_PROVIDER_API_KEY`/`AI_PROVIDER_MODEL` alone (no OpenAI-specific
        # vars set) still works, matching how the generic settings read today.
        return specific_key or settings.AI_PROVIDER_API_KEY, specific_model or settings.AI_PROVIDER_MODEL

    # Used only as the fallback provider: always its own dedicated settings.
    return specific_key, specific_model


class AIGateway:
    def __init__(self, *, settings) -> None:
        self._settings = settings

    def _build_adapter(self, provider: str) -> ProviderAdapter:
        adapter_cls = _ADAPTER_CLASSES.get(provider)
        if adapter_cls is None:
            raise AIUnknownProviderError(f"Unknown AI provider '{provider}' -- supported: {sorted(_ADAPTER_CLASSES)}")
        api_key, model = _resolve_credentials(provider, self._settings)
        return adapter_cls(api_key=api_key, model=model)

    async def complete(self, request: AIGatewayRequest) -> AIGatewayResponse:
        """Runs the request against the configured primary provider, falling
        back to `AI_FALLBACK_PROVIDER` (if set) only for transient failures.
        Raises an AIGatewayError subclass on total failure -- callers
        (insights/ai/provider.py's shim) are responsible for catching that and
        failing safe, exactly as they already do today."""
        primary = self._settings.AI_PROVIDER
        try:
            return await self._call_provider(primary, request)
        except AIGatewayError as exc:
            fallback = getattr(self._settings, "AI_FALLBACK_PROVIDER", "") or ""
            if not fallback or fallback == primary or not _adapter_error_is_fallback_eligible(exc):
                raise
            logger.warning("AI provider '%s' failed (%s), attempting fallback provider '%s'", primary, exc, fallback)
            try:
                response = await self._call_provider(fallback, request)
            except AIGatewayError:
                AI_GATEWAY_REQUESTS.labels(provider=fallback, model=request.model or "unknown", outcome="fallback_failed").inc()
                raise
            AI_GATEWAY_REQUESTS.labels(provider=fallback, model=response.model, outcome="fallback_success").inc()
            return response

    async def _call_provider(self, provider: str, request: AIGatewayRequest) -> AIGatewayResponse:
        required = set(REQUIRED_CAPABILITIES)
        if request.structured_output:
            required.add(Capability.STRUCTURED_OUTPUT)
        validate_capabilities(provider, frozenset(required))

        adapter = self._build_adapter(provider)
        start = time.monotonic()
        try:
            response = await adapter.complete(request)
        except AIGatewayError:
            AI_GATEWAY_LATENCY_SECONDS.labels(provider=provider).observe(time.monotonic() - start)
            AI_GATEWAY_REQUESTS.labels(provider=provider, model=request.model or "unknown", outcome="failed").inc()
            raise
        AI_GATEWAY_LATENCY_SECONDS.labels(provider=provider).observe(time.monotonic() - start)
        AI_GATEWAY_REQUESTS.labels(provider=provider, model=response.model, outcome="success").inc()
        return response

    async def health(self) -> dict[str, bool]:
        """Config-only health snapshot (Step 26) for the primary provider and,
        if configured, the fallback provider. Never makes a real API call."""
        providers = {self._settings.AI_PROVIDER}
        fallback = getattr(self._settings, "AI_FALLBACK_PROVIDER", "") or ""
        if fallback:
            providers.add(fallback)
        result: dict[str, bool] = {}
        for provider in providers:
            try:
                get_provider_info(provider)
                adapter = self._build_adapter(provider)
                result[provider] = await adapter.health_check()
            except AIGatewayError:
                result[provider] = False
        return result


@lru_cache
def get_gateway() -> AIGateway:
    from app.core.config import settings

    return AIGateway(settings=settings)
