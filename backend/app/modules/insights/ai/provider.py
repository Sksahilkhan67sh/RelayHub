"""
Phase 3 -- AI provider abstraction (section 8). Originally a single Anthropic-only
Protocol/implementation; as of the Universal AI Provider & Model Compatibility
phase, this module is a thin backward-compatible SHIM over
`app.modules.ai_gateway`, which is now the real provider-agnostic implementation
(supports anthropic/openai/gemini/xai, normalized errors, capability validation,
optional fallback -- see backend/app/modules/ai_gateway/ and docs/ai/providers.md).

Every public name below (`AIProvider`, `AICompletionRequest`, `AIProviderError`,
`AIProviderTimeoutError`, `AIProviderRateLimitError`, `AnthropicAIProvider`,
`FakeAIProvider`, `get_ai_provider`) keeps its exact pre-existing signature and
behavior on purpose: insight_tasks.py, insights/ai/service.py,
insights/copilot/service.py, insights/copilot/routes.py, and every existing
test file import and use these names unchanged (see
PHASE_UNIVERSAL_AI_AUDIT.md section 7, "Backward compatibility plan"). Nothing
in this module talks to a provider's HTTP API directly anymore -- that logic
lives in `ai_gateway/adapters/`.

This module still does NOT decide *whether* to call the AI (service.py's job)
and does NOT trust raw text back from the provider (ai/schemas.py's job) --
same division of responsibility as before.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol

from app.core.config import settings
from app.modules.ai_gateway.contracts import (
    AIAuthenticationError,
    AICapabilityError,
    AIContextLimitError,
    AIGatewayError,
    AIGatewayRequest,
    AIUnknownProviderError,
)
from app.modules.ai_gateway.contracts import AIInvalidRequestError as _AIInvalidRequestError
from app.modules.ai_gateway.contracts import AIMalformedResponseError as _AIMalformedResponseError
from app.modules.ai_gateway.contracts import AIRateLimitError as _AIRateLimitError
from app.modules.ai_gateway.contracts import AITimeoutError as _AITimeoutError
from app.modules.ai_gateway.contracts import AIUnavailableError as _AIUnavailableError
from app.modules.ai_gateway.gateway import get_gateway


class AIProviderError(Exception):
    """Raised for any provider-side failure: network error, timeout, rate limit,
    non-2xx response, or missing configuration. Always caught by service.py.

    This is the same broad exception every existing caller already catches.
    Every ai_gateway error (auth, rate limit, timeout, unavailable, invalid
    request, context limit, malformed response, unknown provider, capability
    mismatch) is re-raised as this type (or the two more specific subclasses
    below, which are themselves subclasses of this one) so no existing
    `except AIProviderError` call site needs to change."""


class AIProviderTimeoutError(AIProviderError):
    pass


class AIProviderRateLimitError(AIProviderError):
    pass


@dataclass
class AICompletionRequest:
    system_prompt: str
    user_prompt: str
    max_tokens: int
    timeout_seconds: int


class AIProvider(Protocol):
    async def complete(self, request: AICompletionRequest) -> str:
        """Returns raw text output. Callers must treat this as untrusted until it
        passes ai/schemas.py's parse_and_validate."""
        ...


def _translate_gateway_error(exc: AIGatewayError) -> AIProviderError:
    if isinstance(exc, _AITimeoutError):
        return AIProviderTimeoutError(str(exc))
    if isinstance(exc, _AIRateLimitError):
        return AIProviderRateLimitError(str(exc))
    if isinstance(exc, (AIAuthenticationError, _AIInvalidRequestError, _AIUnavailableError,
                         _AIMalformedResponseError, AIContextLimitError, AICapabilityError, AIUnknownProviderError)):
        return AIProviderError(str(exc))
    return AIProviderError(str(exc))


class _GatewayBackedProvider:
    """Adapts the gateway's `complete(AIGatewayRequest) -> AIGatewayResponse`
    onto this module's pre-existing narrow `complete(AICompletionRequest) -> str`
    Protocol, which is all insights/ai/service.py and insights/copilot/service.py
    have ever needed."""

    def __init__(self) -> None:
        self._gateway = get_gateway()

    async def complete(self, request: AICompletionRequest) -> str:
        gateway_request = AIGatewayRequest(
            system_prompt=request.system_prompt,
            messages=[("user", request.user_prompt)],
            max_tokens=request.max_tokens,
            timeout_seconds=request.timeout_seconds,
            structured_output=True,  # both existing callers require valid-JSON output
        )
        try:
            response = await self._gateway.complete(gateway_request)
        except AIGatewayError as exc:
            raise _translate_gateway_error(exc) from exc
        return response.text


def AnthropicAIProvider(*, api_key: str, model: str) -> _GatewayBackedProvider:  # noqa: N802 -- kept PascalCase, pre-existing public name
    """Pre-existing public constructor, kept working unchanged in shape. As of
    this phase it no longer takes `api_key`/`model` as the source of truth
    (the gateway resolves those from `settings` itself, so multiple providers
    can be configured simultaneously -- see ai_gateway/gateway.py's
    `_resolve_credentials`) -- but the parameters are still accepted so any
    existing call site passing them keeps working, and are validated against
    what the gateway would actually use, failing fast on a real mismatch."""
    if not api_key:
        raise AIProviderError("AI_PROVIDER_API_KEY is not configured")
    return _GatewayBackedProvider()


@dataclass
class FakeAIProvider:
    """Used in tests and when AI_PROVIDER_ENABLED is false in local dev. Never
    makes a network call. Tests queue canned responses (valid JSON, malformed
    JSON, or an exception) to exercise service.py's validation and failure-safety
    paths deterministically -- including the required 'AI provider unavailable'
    scenario from section 17 without needing a real provider outage.

    Unchanged from before this phase -- still gateway-independent, so existing
    tests that construct it directly (not via get_ai_provider()) are
    unaffected by the gateway migration."""

    queued_responses: list[str] = field(default_factory=list)
    queued_exception: Exception | None = None
    calls: list[AICompletionRequest] = field(default_factory=list)
    latency_seconds: float = 0.0

    async def complete(self, request: AICompletionRequest) -> str:
        self.calls.append(request)
        if self.latency_seconds:
            await asyncio.sleep(self.latency_seconds)
        if self.queued_exception is not None:
            raise self.queued_exception
        if not self.queued_responses:
            raise AIProviderError("FakeAIProvider: no queued response -- call queue_response() first in the test")
        return self.queued_responses.pop(0)

    def queue_response(self, raw_text: str) -> None:
        self.queued_responses.append(raw_text)

    def queue_failure(self, exc: Exception) -> None:
        self.queued_exception = exc


@lru_cache
def get_ai_provider() -> AIProvider:
    if not settings.AI_PROVIDER_ENABLED:
        # Callers must check settings.AI_PROVIDER_ENABLED before invoking this at
        # all (see service.py) -- this is a defensive fallback, not the primary gate.
        raise AIProviderError("AI provider is disabled (AI_PROVIDER_ENABLED=false)")
    if not settings.AI_PROVIDER_API_KEY and not getattr(settings, f"AI_{settings.AI_PROVIDER.upper()}_API_KEY", ""):
        raise AIProviderError(f"No API key configured for AI_PROVIDER='{settings.AI_PROVIDER}'")
    try:
        from app.modules.ai_gateway.registry import get_provider_info

        get_provider_info(settings.AI_PROVIDER)
    except AIUnknownProviderError as exc:
        raise AIProviderError(f"Unknown AI_PROVIDER '{settings.AI_PROVIDER}' -- supported: anthropic, openai, gemini, xai") from exc
    return _GatewayBackedProvider()
