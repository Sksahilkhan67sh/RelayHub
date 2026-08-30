"""
Google Gemini adapter (Step 7). Gemini's generateContent API has meaningfully
different semantics from Anthropic/OpenAI's chat-message shape (Step 7:
"Do not assume Gemini behaves exactly like OpenAI or Anthropic"):

  - The API key is a query parameter, not an Authorization header.
  - "system" is a top-level `system_instruction` field, not a message role.
  - There's no native "assistant" role name -- Gemini calls it "model".
  - Content is a list of `parts` (each `{"text": ...}`), not a flat string.
  - Usage lives under `usageMetadata` with different field names.
  - JSON-mode is `generationConfig.responseMimeType = "application/json"`,
    not a `response_format` object.

This adapter translates RelayHub's normalized AIGatewayRequest into that shape
and translates the response back, so none of that leaks into the gateway or
callers.

UNVERIFIED against the real Gemini API in this environment -- no credentials
and no outbound network to generativelanguage.googleapis.com available here
(see PHASE_UNIVERSAL_AI_AUDIT.md, "Risks"). Built strictly from Gemini's
documented generateContent request/response shape and covered by adapter
tests using a mocked transport.
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

_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Gemini has no "assistant" role name.
_ROLE_MAP = {"assistant": "model", "user": "user"}


class GeminiAdapter:
    provider_name = "gemini"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise AIAuthenticationError("GEMINI_API_KEY / AI_GEMINI_API_KEY is not configured")
        self._api_key = api_key
        self.model = model

    async def health_check(self) -> bool:
        return bool(self._api_key) and bool(self.model)

    async def complete(self, request: AIGatewayRequest) -> AIGatewayResponse:
        model = request.model or self.model
        url = f"{_API_BASE}/{model}:generateContent"

        contents = [
            {"role": _ROLE_MAP.get(role, "user"), "parts": [{"text": content}]} for role, content in request.messages
        ]
        generation_config: dict = {"maxOutputTokens": request.max_tokens}
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.structured_output:
            generation_config["responseMimeType"] = "application/json"

        body: dict = {
            "system_instruction": {"parts": [{"text": request.system_prompt}]},
            "contents": contents,
            "generationConfig": generation_config,
        }

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(url, params={"key": self._api_key}, json=body)
        except httpx.TimeoutException as exc:
            raise AITimeoutError(f"Gemini request timed out after {request.timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise AIUnavailableError(f"Gemini request failed: {exc}") from exc
        latency = time.monotonic() - start

        _raise_for_status(response)

        try:
            data = response.json()
        except ValueError as exc:
            raise AIMalformedResponseError(f"Gemini returned non-JSON response: {exc}") from exc

        try:
            candidate = data["candidates"][0]
            parts = candidate["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise AIMalformedResponseError(f"Unexpected Gemini response shape: {exc}") from exc

        if not text:
            raise AIMalformedResponseError("Gemini returned no text content")

        usage_raw = data.get("usageMetadata") or {}
        usage = AIUsage(
            input_tokens=usage_raw.get("promptTokenCount"),
            output_tokens=usage_raw.get("candidatesTokenCount"),
            total_tokens=usage_raw.get("totalTokenCount"),
        )

        return AIGatewayResponse(
            text=text,
            provider="gemini",
            model=model,
            usage=usage,
            finish_reason=candidate.get("finishReason"),
            latency_seconds=latency,
        )


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    detail = response.text[:500]
    if response.status_code in (401, 403):
        raise AIAuthenticationError(f"gemini authentication failed (HTTP {response.status_code}): {detail}")
    if response.status_code == 429:
        raise AIRateLimitError("gemini rate limit exceeded")
    if response.status_code == 400 and ("context" in detail.lower() or "token" in detail.lower()):
        raise AIContextLimitError(f"gemini request exceeded context limit: {detail}")
    if response.status_code in (400, 422):
        raise AIInvalidRequestError(f"gemini rejected the request (HTTP {response.status_code}): {detail}")
    if response.status_code >= 500:
        raise AIUnavailableError(f"gemini returned HTTP {response.status_code}: {detail}")
    raise AIProviderError(f"gemini returned HTTP {response.status_code}: {detail}")
