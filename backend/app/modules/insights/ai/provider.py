"""
Phase 3 -- AI provider abstraction (section 8). Same shape as every other external
dependency in this codebase (stripe_client, notification_client, queue_client): a
Protocol, a real implementation, and an injectable fake for tests. RelayHub is
never tightly coupled to one AI vendor -- provider/model/timeout/token-limit/
enable-flag are all config (see Settings.AI_PROVIDER_*), and swapping providers
means writing one new class here, not touching insight_tasks.py or rca.py.

This module does NOT decide *whether* to call the AI (that's service.py's job,
gated on "incident candidate", never on raw events) and does NOT trust raw text
back from the provider (that's ai/schemas.py's job). This module's only
responsibility is "given a prompt, return raw text from the configured provider,
or raise on failure/timeout" -- deliberately thin.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol

from app.core.config import settings


class AIProviderError(Exception):
    """Raised for any provider-side failure: network error, timeout, rate limit,
    non-2xx response, or missing configuration. Always caught by service.py."""


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


class AnthropicAIProvider:
    """Real provider implementation. Uses the Anthropic Messages API directly
    (httpx) rather than the SDK, matching this codebase's existing preference for
    thin direct HTTP calls in external-service clients (see delivery/executor.py)."""

    _API_URL = "https://api.anthropic.com/v1/messages"
    _API_VERSION = "2023-06-01"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise AIProviderError("AI_PROVIDER_API_KEY is not configured")
        self._api_key = api_key
        self._model = model

    async def complete(self, request: AICompletionRequest) -> str:
        import httpx

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self._API_VERSION,
            "content-type": "application/json",
        }
        body = {
            "model": self._model,
            "max_tokens": request.max_tokens,
            "system": request.system_prompt,
            "messages": [{"role": "user", "content": request.user_prompt}],
        }

        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(self._API_URL, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError(f"AI provider request timed out after {request.timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f"AI provider request failed: {exc}") from exc

        if response.status_code == 429:
            raise AIProviderRateLimitError("AI provider rate limit exceeded")
        if response.status_code >= 400:
            raise AIProviderError(f"AI provider returned HTTP {response.status_code}: {response.text[:500]}")

        data = response.json()
        try:
            blocks = data["content"]
            text = "".join(block["text"] for block in blocks if block.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise AIProviderError(f"Unexpected AI provider response shape: {exc}") from exc

        if not text:
            raise AIProviderError("AI provider returned no text content")
        return text


@dataclass
class FakeAIProvider:
    """Used in tests and when AI_PROVIDER_ENABLED is false in local dev. Never
    makes a network call. Tests queue canned responses (valid JSON, malformed
    JSON, or an exception) to exercise service.py's validation and failure-safety
    paths deterministically -- including the required 'AI provider unavailable'
    scenario from section 17 without needing a real provider outage."""

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
    if settings.AI_PROVIDER == "anthropic":
        return AnthropicAIProvider(api_key=settings.AI_PROVIDER_API_KEY, model=settings.AI_PROVIDER_MODEL)
    raise AIProviderError(f"Unknown AI_PROVIDER '{settings.AI_PROVIDER}' -- supported: anthropic")
