"""
Anthropic adapter (Step 5). This is the pre-existing, already-working
AnthropicAIProvider from insights/ai/provider.py, moved here unchanged in
behavior and re-shaped to return AIGatewayResponse instead of a bare str, plus
normalized errors instead of the old three-class taxonomy. Same httpx-direct
approach (no SDK dependency added), same endpoint, same auth header shape.
"""

from __future__ import annotations

import time

import httpx

from app.modules.ai_gateway.contracts import (
    AIAuthenticationError,
    AIContextLimitError,
    AIGatewayRequest,
    AIGatewayResponse,
    AIInvalidRequestError,
    AIMalformedResponseError,
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
    AIUnavailableError,
    AIUsage,
)

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"


class AnthropicAdapter:
    provider_name = "anthropic"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise AIAuthenticationError("ANTHROPIC_API_KEY / AI_PROVIDER_API_KEY is not configured")
        self._api_key = api_key
        self.model = model

    async def health_check(self) -> bool:
        return bool(self._api_key) and bool(self.model)

    async def complete(self, request: AIGatewayRequest) -> AIGatewayResponse:
        model = request.model or self.model
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }
        body: dict = {
            "model": model,
            "max_tokens": request.max_tokens,
            "system": request.system_prompt,
            "messages": [{"role": role, "content": content} for role, content in request.messages],
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(_API_URL, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise AITimeoutError(f"Anthropic request timed out after {request.timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise AIUnavailableError(f"Anthropic request failed: {exc}") from exc
        latency = time.monotonic() - start

        _raise_for_status(response, provider="anthropic")

        try:
            data = response.json()
        except ValueError as exc:
            raise AIMalformedResponseError(f"Anthropic returned non-JSON response: {exc}") from exc

        try:
            blocks = data["content"]
            text = "".join(block["text"] for block in blocks if block.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise AIMalformedResponseError(f"Unexpected Anthropic response shape: {exc}") from exc

        if not text:
            raise AIMalformedResponseError("Anthropic returned no text content")

        usage_raw = data.get("usage") or {}
        input_tokens = usage_raw.get("input_tokens")
        output_tokens = usage_raw.get("output_tokens")
        usage = AIUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(input_tokens + output_tokens) if input_tokens is not None and output_tokens is not None else None,
        )

        return AIGatewayResponse(
            text=text,
            provider="anthropic",
            model=data.get("model", model),
            usage=usage,
            finish_reason=data.get("stop_reason"),
            latency_seconds=latency,
            request_id=data.get("id"),
        )


def _raise_for_status(response: httpx.Response, *, provider: str) -> None:
    if response.status_code < 400:
        return
    detail = response.text[:500]
    if response.status_code in (401, 403):
        raise AIAuthenticationError(f"{provider} authentication failed (HTTP {response.status_code}): {detail}")
    if response.status_code == 429:
        raise AIRateLimitError(f"{provider} rate limit exceeded")
    if response.status_code == 400 and "context" in detail.lower():
        raise AIContextLimitError(f"{provider} request exceeded context limit: {detail}")
    if response.status_code in (400, 422):
        raise AIInvalidRequestError(f"{provider} rejected the request (HTTP {response.status_code}): {detail}")
    if response.status_code >= 500:
        raise AIUnavailableError(f"{provider} returned HTTP {response.status_code}: {detail}")
    raise AIProviderError(f"{provider} returned HTTP {response.status_code}: {detail}")
