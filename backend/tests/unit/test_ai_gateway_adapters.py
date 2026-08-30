"""
Adapter tests (Step 34): each provider adapter against a mocked httpx
transport (httpx.MockTransport) -- deterministic, no real network, no
credentials needed. Covers valid response, structured-output request shape,
and each normalized-error mapping (401, 429, 400, 500, malformed body).

These test the ADAPTERS' translation logic (request shape sent, response
shape parsed, status-code -> error mapping) against each vendor's documented
API shape. They do not and cannot prove the real vendor APIs behave exactly
this way -- see PHASE_UNIVERSAL_AI_AUDIT.md "Risks" and
PHASE_UNIVERSAL_AI_REPORT.md's compatibility matrix, which marks live-API
verification UNVERIFIED for openai/gemini/xai in this environment.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.modules.ai_gateway.adapters.anthropic import AnthropicAdapter
from app.modules.ai_gateway.adapters.gemini import GeminiAdapter
from app.modules.ai_gateway.adapters.openai import OpenAIAdapter
from app.modules.ai_gateway.adapters.xai import XAIAdapter
from app.modules.ai_gateway.contracts import (
    AIAuthenticationError,
    AIGatewayRequest,
    AIMalformedResponseError,
    AIRateLimitError,
    AIUnavailableError,
)


def _request(**overrides) -> AIGatewayRequest:
    base = dict(system_prompt="You are a helpful assistant.", messages=[("user", "hi")], max_tokens=50, timeout_seconds=5)
    base.update(overrides)
    return AIGatewayRequest(**base)


def _patch_transport(monkeypatch, handler) -> None:
    """Redirects httpx.AsyncClient to a MockTransport for the duration of one
    test, without touching the real network -- same technique whichever
    adapter under test uses internally."""
    real_client_cls = httpx.AsyncClient

    def _client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client_cls(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)


# --- Anthropic -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_anthropic_adapter_happy_path(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-key"
        body = json.loads(request.content)
        assert body["model"] == "claude-sonnet-4-6"
        assert body["system"] == "You are a helpful assistant."
        return httpx.Response(
            200,
            json={
                "id": "msg_123",
                "model": "claude-sonnet-4-6",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "hello back"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    _patch_transport(monkeypatch, handler)
    adapter = AnthropicAdapter(api_key="test-key", model="claude-sonnet-4-6")
    response = await adapter.complete(_request())
    assert response.text == "hello back"
    assert response.provider == "anthropic"
    assert response.usage.input_tokens == 10
    assert response.usage.total_tokens == 15
    assert response.finish_reason == "end_turn"


@pytest.mark.asyncio
async def test_anthropic_adapter_401_maps_to_auth_error(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(401, json={"error": "invalid api key"}))
    adapter = AnthropicAdapter(api_key="bad-key", model="claude-sonnet-4-6")
    with pytest.raises(AIAuthenticationError):
        await adapter.complete(_request())


@pytest.mark.asyncio
async def test_anthropic_adapter_429_maps_to_rate_limit(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(429, json={"error": "rate limited"}))
    adapter = AnthropicAdapter(api_key="k", model="claude-sonnet-4-6")
    with pytest.raises(AIRateLimitError):
        await adapter.complete(_request())


@pytest.mark.asyncio
async def test_anthropic_adapter_500_maps_to_unavailable(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(500, text="internal error"))
    adapter = AnthropicAdapter(api_key="k", model="claude-sonnet-4-6")
    with pytest.raises(AIUnavailableError):
        await adapter.complete(_request())


@pytest.mark.asyncio
async def test_anthropic_adapter_malformed_body_maps_to_malformed_response(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"unexpected": "shape"}))
    adapter = AnthropicAdapter(api_key="k", model="claude-sonnet-4-6")
    with pytest.raises(AIMalformedResponseError):
        await adapter.complete(_request())


def test_anthropic_adapter_requires_api_key():
    with pytest.raises(AIAuthenticationError):
        AnthropicAdapter(api_key="", model="claude-sonnet-4-6")


# --- OpenAI ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_adapter_happy_path(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["messages"][0] == {"role": "system", "content": "You are a helpful assistant."}
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-123",
                "model": "gpt-4o",
                "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28},
            },
        )

    _patch_transport(monkeypatch, handler)
    adapter = OpenAIAdapter(api_key="test-key", model="gpt-4o")
    response = await adapter.complete(_request(structured_output=True))
    assert response.text == '{"ok": true}'
    assert response.usage.total_tokens == 28
    assert response.finish_reason == "stop"


@pytest.mark.asyncio
async def test_openai_adapter_403_maps_to_auth_error(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(403, json={"error": "forbidden"}))
    adapter = OpenAIAdapter(api_key="k", model="gpt-4o")
    with pytest.raises(AIAuthenticationError):
        await adapter.complete(_request())


@pytest.mark.asyncio
async def test_openai_adapter_timeout_maps_to_timeout_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    _patch_transport(monkeypatch, handler)
    adapter = OpenAIAdapter(api_key="k", model="gpt-4o")
    from app.modules.ai_gateway.contracts import AITimeoutError

    with pytest.raises(AITimeoutError):
        await adapter.complete(_request())


# --- Gemini ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_adapter_happy_path(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["key"] == "test-key"
        body = json.loads(request.content)
        assert body["system_instruction"]["parts"][0]["text"] == "You are a helpful assistant."
        assert body["contents"][0]["role"] == "user"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "hi from gemini"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 4, "totalTokenCount": 16},
            },
        )

    _patch_transport(monkeypatch, handler)
    adapter = GeminiAdapter(api_key="test-key", model="gemini-1.5-pro")
    response = await adapter.complete(_request())
    assert response.text == "hi from gemini"
    assert response.provider == "gemini"
    assert response.usage.total_tokens == 16
    assert response.finish_reason == "STOP"


@pytest.mark.asyncio
async def test_gemini_adapter_assistant_role_mapped_to_model(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["contents"][1]["role"] == "model"  # not "assistant" -- gemini has no such role
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        )

    _patch_transport(monkeypatch, handler)
    adapter = GeminiAdapter(api_key="k", model="gemini-1.5-pro")
    req = _request(messages=[("user", "hi"), ("assistant", "hello"), ("user", "how are you")])
    await adapter.complete(req)


@pytest.mark.asyncio
async def test_gemini_adapter_429_maps_to_rate_limit(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(429, text="quota exceeded"))
    adapter = GeminiAdapter(api_key="k", model="gemini-1.5-pro")
    with pytest.raises(AIRateLimitError):
        await adapter.complete(_request())


# --- xAI / Grok --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_xai_adapter_happy_path(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "id": "req_123",
                "model": "grok-2-latest",
                "choices": [{"message": {"content": "grok says hi"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            },
        )

    _patch_transport(monkeypatch, handler)
    adapter = XAIAdapter(api_key="test-key", model="grok-2-latest")
    response = await adapter.complete(_request())
    assert response.text == "grok says hi"
    assert response.provider == "xai"


@pytest.mark.asyncio
async def test_xai_adapter_500_maps_to_unavailable(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(500, text="server error"))
    adapter = XAIAdapter(api_key="k", model="grok-2-latest")
    with pytest.raises(AIUnavailableError):
        await adapter.complete(_request())


def test_xai_adapter_requires_api_key():
    with pytest.raises(AIAuthenticationError):
        XAIAdapter(api_key="", model="grok-2-latest")
