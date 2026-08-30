"""
xAI/Grok adapter (Step 8). xAI's API is OpenAI-Chat-Completions-compatible
(same request/response envelope), so this adapter mirrors openai.py rather
than sharing a base class with it -- kept as a separate, independently
readable/editable module per-provider, matching this codebase's existing
preference for explicit per-external-service clients over shared inheritance
(see delivery/executor.py vs. billing clients).

UNVERIFIED against the real xAI API in this environment -- no credentials and
no outbound network to api.x.ai available here (see PHASE_UNIVERSAL_AI_AUDIT.md,
"Risks"). Built strictly from xAI's documented OpenAI-compatible request/
response shape and covered by adapter tests using a mocked transport.
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

_API_URL = "https://api.x.ai/v1/chat/completions"


class XAIAdapter:
    provider_name = "xai"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise AIAuthenticationError("XAI_API_KEY / AI_XAI_API_KEY is not configured")
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
            body["response_format"] = {"type": "json_object"}

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(_API_URL, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise AITimeoutError(f"xAI request timed out after {request.timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise AIUnavailableError(f"xAI request failed: {exc}") from exc
        latency = time.monotonic() - start

        _raise_for_status(response)

        try:
            data = response.json()
        except ValueError as exc:
            raise AIMalformedResponseError(f"xAI returned non-JSON response: {exc}") from exc

        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIMalformedResponseError(f"Unexpected xAI response shape: {exc}") from exc

        if not text:
            raise AIMalformedResponseError("xAI returned no text content")

        usage_raw = data.get("usage") or {}
        usage = AIUsage(
            input_tokens=usage_raw.get("prompt_tokens"),
            output_tokens=usage_raw.get("completion_tokens"),
            total_tokens=usage_raw.get("total_tokens"),
        )

        return AIGatewayResponse(
            text=text,
            provider="xai",
            model=data.get("model", model),
            usage=usage,
            finish_reason=choice.get("finish_reason"),
            latency_seconds=latency,
            request_id=data.get("id"),
        )


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    detail = response.text[:500]
    if response.status_code in (401, 403):
        raise AIAuthenticationError(f"xai authentication failed (HTTP {response.status_code}): {detail}")
    if response.status_code == 429:
        raise AIRateLimitError("xai rate limit exceeded")
    if response.status_code == 400 and "context" in detail.lower():
        raise AIContextLimitError(f"xai request exceeded context limit: {detail}")
    if response.status_code in (400, 422):
        raise AIInvalidRequestError(f"xai rejected the request (HTTP {response.status_code}): {detail}")
    if response.status_code >= 500:
        raise AIUnavailableError(f"xai returned HTTP {response.status_code}: {detail}")
    raise AIProviderError(f"xai returned HTTP {response.status_code}: {detail}")
