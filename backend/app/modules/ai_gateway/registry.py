"""
Provider/model registry (Step 10, Step 11).

Deliberately NOT a hardcoded list of every model a vendor currently ships --
model names churn constantly and a hardcoded list goes stale (per Step 10's
explicit warning). Instead:

  - The set of SUPPORTED PROVIDERS (which adapters exist) is a fixed, small
    enum-like registry below, because that's genuinely stable -- adding a
    provider is a code change (a new adapter) regardless.
  - The MODEL for each provider is always config-driven (AI_PROVIDER_MODEL /
    AI_<PROVIDER>_MODEL), never chosen from a hardcoded list.
  - CAPABILITIES are recorded per *provider family*, not per exact model
    string, since RelayHub only ever needs to know "can this provider do
    chat + structured output", not fine-grained per-model feature flags. This
    keeps the registry from needing an update every time a vendor ships a new
    model name.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.ai_gateway.contracts import AICapabilityError, AIUnknownProviderError, Capability


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    default_model_env: str  # which Settings field holds this provider's configured model, for error messages/docs only
    capabilities: frozenset[Capability]


# Capabilities reflect what RelayHub's adapters actually implement for that
# provider today (Step 11: "do NOT assume every model supports everything").
# All four support plain chat + structured (JSON-mode-or-equivalent) output --
# that's the only pair RelayHub's two AI features need. None of the adapters
# implement streaming/tool_use/vision/embeddings in this phase (Step 23), so
# those are left off every provider's set rather than claimed speculatively.
_PROVIDERS: dict[str, ProviderInfo] = {
    "anthropic": ProviderInfo(
        name="anthropic",
        default_model_env="AI_PROVIDER_MODEL",
        capabilities=frozenset({Capability.CHAT, Capability.STRUCTURED_OUTPUT, Capability.LONG_CONTEXT}),
    ),
    "openai": ProviderInfo(
        name="openai",
        default_model_env="AI_OPENAI_MODEL",
        capabilities=frozenset({Capability.CHAT, Capability.STRUCTURED_OUTPUT}),
    ),
    "gemini": ProviderInfo(
        name="gemini",
        default_model_env="AI_GEMINI_MODEL",
        capabilities=frozenset({Capability.CHAT, Capability.STRUCTURED_OUTPUT, Capability.LONG_CONTEXT}),
    ),
    "xai": ProviderInfo(
        name="xai",
        default_model_env="AI_XAI_MODEL",
        capabilities=frozenset({Capability.CHAT, Capability.STRUCTURED_OUTPUT}),
    ),
}

REQUIRED_CAPABILITIES: frozenset[Capability] = frozenset({Capability.CHAT})
# Callers set AIGatewayRequest.structured_output=True (both insights/ai and
# copilot always do) to additionally require Capability.STRUCTURED_OUTPUT --
# see gateway.py's _validate_capabilities.


def get_provider_info(provider: str) -> ProviderInfo:
    info = _PROVIDERS.get(provider)
    if info is None:
        raise AIUnknownProviderError(f"Unknown AI provider '{provider}' -- supported: {sorted(_PROVIDERS)}")
    return info


def supported_providers() -> list[str]:
    return sorted(_PROVIDERS)


def validate_capabilities(provider: str, required: frozenset[Capability]) -> None:
    info = get_provider_info(provider)
    missing = required - info.capabilities
    if missing:
        raise AICapabilityError(
            f"Provider '{provider}' does not support required capability/capabilities: "
            f"{sorted(c.value for c in missing)}"
        )
