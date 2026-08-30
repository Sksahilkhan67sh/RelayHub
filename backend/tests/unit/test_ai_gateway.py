"""
Gateway-level tests (Step 33): provider selection, model selection, capability
validation, fallback, configuration, and error propagation -- all against the
FakeAdapter (no HTTP), plus the insights.ai.provider backward-compat shim.
"""

from __future__ import annotations

import pytest

from app.modules.ai_gateway.contracts import (
    AICapabilityError,
    AIGatewayRequest,
    AIRateLimitError,
    AIUnavailableError,
    AIUnknownProviderError,
)
from app.modules.ai_gateway.fake import FakeAdapter
from app.modules.ai_gateway.gateway import AIGateway, _adapter_error_is_fallback_eligible, _resolve_credentials
from app.modules.ai_gateway.registry import Capability, get_provider_info, supported_providers, validate_capabilities
from app.modules.insights.ai.provider import AIProviderError, AIProviderRateLimitError, FakeAIProvider


class _Settings:
    """Minimal settings stand-in -- only the fields ai_gateway actually reads."""

    def __init__(self, **overrides):
        self.AI_PROVIDER = "anthropic"
        self.AI_PROVIDER_API_KEY = "generic-key"
        self.AI_PROVIDER_MODEL = "claude-sonnet-4-6"
        self.AI_FALLBACK_PROVIDER = ""
        self.AI_OPENAI_API_KEY = ""
        self.AI_OPENAI_MODEL = "gpt-4o"
        self.AI_GEMINI_API_KEY = ""
        self.AI_GEMINI_MODEL = "gemini-1.5-pro"
        self.AI_XAI_API_KEY = ""
        self.AI_XAI_MODEL = "grok-2-latest"
        for k, v in overrides.items():
            setattr(self, k, v)


def _request(**overrides) -> AIGatewayRequest:
    base = dict(system_prompt="sys", messages=[("user", "hello")], max_tokens=100, timeout_seconds=10)
    base.update(overrides)
    return AIGatewayRequest(**base)


# --- registry ----------------------------------------------------------------


def test_supported_providers_lists_all_four():
    assert supported_providers() == ["anthropic", "gemini", "openai", "xai"]


def test_unknown_provider_raises():
    with pytest.raises(AIUnknownProviderError):
        get_provider_info("cohere")


def test_all_providers_support_chat_and_structured_output():
    for provider in supported_providers():
        validate_capabilities(provider, frozenset({Capability.CHAT, Capability.STRUCTURED_OUTPUT}))


def test_capability_not_supported_raises():
    with pytest.raises(AICapabilityError):
        validate_capabilities("openai", frozenset({Capability.VISION}))


# --- credential resolution (backward compatibility, Step 31) -----------------


def test_anthropic_uses_generic_settings_unchanged():
    settings = _Settings()
    key, model = _resolve_credentials("anthropic", settings)
    assert (key, model) == ("generic-key", "claude-sonnet-4-6")


def test_primary_openai_falls_back_to_generic_key_when_no_specific_key():
    # AI_OPENAI_MODEL always has its own sensible default ("gpt-4o"), so the
    # model always resolves from the provider-specific setting; only the API
    # KEY (which has no per-provider default) falls back to the generic one.
    settings = _Settings(AI_PROVIDER="openai", AI_PROVIDER_API_KEY="sk-generic", AI_PROVIDER_MODEL="gpt-4o-mini")
    key, model = _resolve_credentials("openai", settings)
    assert (key, model) == ("sk-generic", "gpt-4o")


def test_primary_openai_prefers_specific_settings_when_set():
    settings = _Settings(AI_PROVIDER="openai", AI_OPENAI_API_KEY="sk-specific", AI_OPENAI_MODEL="gpt-4o")
    key, model = _resolve_credentials("openai", settings)
    assert (key, model) == ("sk-specific", "gpt-4o")


def test_fallback_only_provider_never_uses_generic_settings():
    settings = _Settings(AI_PROVIDER="anthropic", AI_FALLBACK_PROVIDER="openai")
    key, model = _resolve_credentials("openai", settings)
    # generic AI_PROVIDER_API_KEY belongs to anthropic (the primary) here, not openai
    assert key == ""
    assert model == "gpt-4o"


# --- gateway: happy path, capability gating, unknown provider ----------------


@pytest.mark.asyncio
async def test_gateway_happy_path_records_success():
    gateway = AIGateway(settings=_Settings())
    fake = FakeAdapter(provider_name="anthropic", model="claude-sonnet-4-6")
    fake.queue_response('{"ok": true}')
    gateway._ADAPTER_OVERRIDE_FOR_TEST = None  # documents that we monkeypatch _build_adapter below
    gateway._build_adapter = lambda provider: fake  # type: ignore[method-assign]

    response = await gateway.complete(_request(structured_output=True))
    assert response.text == '{"ok": true}'
    assert response.provider == "anthropic"
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_gateway_unknown_primary_provider_raises():
    gateway = AIGateway(settings=_Settings(AI_PROVIDER="cohere"))
    with pytest.raises(AIUnknownProviderError):
        await gateway.complete(_request())


# --- fallback (Step 19) -------------------------------------------------------


def test_fallback_eligibility_excludes_auth_and_invalid_request():
    from app.modules.ai_gateway.contracts import AIAuthenticationError, AIInvalidRequestError, AITimeoutError

    assert _adapter_error_is_fallback_eligible(AITimeoutError("x")) is True
    assert _adapter_error_is_fallback_eligible(AIRateLimitError("x")) is True
    assert _adapter_error_is_fallback_eligible(AIUnavailableError("x")) is True
    assert _adapter_error_is_fallback_eligible(AIAuthenticationError("x")) is False
    assert _adapter_error_is_fallback_eligible(AIInvalidRequestError("x")) is False


@pytest.mark.asyncio
async def test_gateway_falls_back_on_transient_failure():
    primary = FakeAdapter(provider_name="anthropic")
    primary.queue_failure(AIUnavailableError("anthropic is down"))
    fallback = FakeAdapter(provider_name="openai")
    fallback.queue_response('{"ok": true}')

    gateway = AIGateway(settings=_Settings(AI_FALLBACK_PROVIDER="openai"))
    adapters = {"anthropic": primary, "openai": fallback}
    gateway._build_adapter = lambda provider: adapters[provider]  # type: ignore[method-assign]

    response = await gateway.complete(_request(structured_output=True))
    assert response.text == '{"ok": true}'
    assert response.provider == "openai"
    assert len(primary.calls) == 1
    assert len(fallback.calls) == 1


@pytest.mark.asyncio
async def test_gateway_does_not_fall_back_on_auth_error():
    from app.modules.ai_gateway.contracts import AIAuthenticationError

    primary = FakeAdapter(provider_name="anthropic")
    primary.queue_failure(AIAuthenticationError("bad key"))
    fallback = FakeAdapter(provider_name="openai")
    fallback.queue_response('{"ok": true}')

    gateway = AIGateway(settings=_Settings(AI_FALLBACK_PROVIDER="openai"))
    adapters = {"anthropic": primary, "openai": fallback}
    gateway._build_adapter = lambda provider: adapters[provider]  # type: ignore[method-assign]

    with pytest.raises(AIAuthenticationError):
        await gateway.complete(_request())
    assert len(fallback.calls) == 0  # never attempted


@pytest.mark.asyncio
async def test_gateway_no_fallback_configured_raises_primary_error():
    primary = FakeAdapter(provider_name="anthropic")
    primary.queue_failure(AIUnavailableError("down"))
    gateway = AIGateway(settings=_Settings())  # AI_FALLBACK_PROVIDER="" by default
    gateway._build_adapter = lambda provider: primary  # type: ignore[method-assign]

    with pytest.raises(AIUnavailableError):
        await gateway.complete(_request())


# --- health check (Step 26) ---------------------------------------------------


@pytest.mark.asyncio
async def test_health_check_is_config_only_never_calls_complete():
    fake = FakeAdapter(provider_name="anthropic")  # no queued response/exception on purpose
    gateway = AIGateway(settings=_Settings())
    gateway._build_adapter = lambda provider: fake  # type: ignore[method-assign]

    result = await gateway.health()
    assert result == {"anthropic": True}
    assert fake.calls == []  # health() must never invoke complete()


# --- backward-compatible shim (insights.ai.provider) --------------------------


@pytest.mark.asyncio
async def test_fake_ai_provider_still_works_standalone():
    """FakeAIProvider is gateway-independent -- existing tests construct it
    directly without touching the gateway at all."""
    fake = FakeAIProvider()
    fake.queue_response("hello")
    from app.modules.insights.ai.provider import AICompletionRequest

    result = await fake.complete(AICompletionRequest(system_prompt="s", user_prompt="u", max_tokens=10, timeout_seconds=5))
    assert result == "hello"


def test_shim_error_hierarchy_unchanged():
    assert issubclass(AIProviderRateLimitError, AIProviderError)
