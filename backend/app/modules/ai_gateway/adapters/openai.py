"""
OpenAI adapter (Step 6). Uses the Chat Completions endpoint directly via
httpx, matching the codebase's existing thin-direct-HTTP-client convention
(see anthropic.py, delivery/executor.py) rather than adding the openai SDK
as a new dependency.

UNVERIFIED against the real OpenAI API in this environment -- no credentials
and no outbound network to api.openai.com available here (see
PHASE_UNIVERSAL_AI_AUDIT.md, "Risks"). Built strictly from OpenAI's documented
Chat Completions request/response shape and covered by adapter tests using a
mocked transport (test_ai_gateway_adapters.py).
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

_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIAdapter:
    provider_name = "openai"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise AIAuthenticationError("OPENAI_API_KEY / AI_OPENAI_API_KEY is not configured")
        self._api_key = api_key
        self.model = model

    async def health_check(self) -> bool:
        return bool(self._api_key) and bool(self.model)

    async def complete(self, request: AIGatewayRequest) -> AIGatewayResponse:
        model = request.model or self.model
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        messages = [{"role": "system", "content": request.system_prompt}]
        messages.extend({"role": role, "content": content} for role, content in request.messages)

        body: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.structured_output:
            # JSON mode -- caller (insights/ai/schemas.py, copilot/schemas.py) still
            # independently validates the parsed content; this only nudges the
            # provider toward valid JSON, it is not the trust boundary.
            body["response_format"] = {"type": "json_object"}

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(_API_URL, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise AITimeoutError(f"OpenAI request timed out after {request.timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise AIUnavailableError(f"OpenAI request failed: {exc}") from exc
        latency = time.monotonic() - start

        _raise_for_status(response, provider="openai")

        try:
            data = response.json()
        except ValueError as exc:
            raise AIMalformedResponseError(f"OpenAI returned non-JSON response: {exc}") from exc

        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIMalformedResponseError(f"Unexpected OpenAI response shape: {exc}") from exc

        if not text:
            raise AIMalformedResponseError("OpenAI returned no text content")

        usage_raw = data.get("usage") or {}
        usage = AIUsage(
            input_tokens=usage_raw.get("prompt_tokens"),
            output_tokens=usage_raw.get("completion_tokens"),
            total_tokens=usage_raw.get("total_tokens"),
        )

        return AIGatewayResponse(
            text=text,
            provider="openai",
            model=data.get("model", model),
            usage=usage,
            finish_reason=choice.get("finish_reason"),
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
