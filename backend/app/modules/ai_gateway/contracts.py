"""
Provider-neutral contracts for the AI gateway: request, response, error taxonomy,
and capability enum. Nothing in this file imports httpx or any provider SDK --
it is pure data shape, shared by every adapter and by the gateway itself.

Design note: this intentionally covers only what RelayHub's two AI features
(incident analysis, copilot chat) actually use today -- single-turn-per-call
text completion with an optional structured-output contract enforced by the
CALLER (insights/ai/schemas.py, copilot/schemas.py), not by the gateway itself.
Streaming, tool_use, vision, and embeddings are named in Capability for the
registry's sake (Step 11) but are not implemented -- Copilot doesn't need them
(Step 23: "do NOT implement streaming simply because a provider supports it").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Capability(str, Enum):
    """Only capabilities RelayHub's AI features actually depend on are enforced
    by the gateway (CHAT, STRUCTURED_OUTPUT). The rest exist so the registry can
    describe a model accurately and so a future feature has somewhere to declare
    a new requirement without inventing a new mechanism."""

    CHAT = "chat"
    STRUCTURED_OUTPUT = "structured_output"
    TOOL_USE = "tool_use"
    VISION = "vision"
    STREAMING = "streaming"
    EMBEDDINGS = "embeddings"
    LONG_CONTEXT = "long_context"
    REASONING = "reasoning"


@dataclass
class AIGatewayRequest:
    """Provider-neutral request. Adapters translate this into whatever shape
    their vendor's API wants and never receive anything else from the gateway."""

    system_prompt: str
    messages: list[tuple[str, str]]  # (role, content) -- role is "user" or "assistant"
    max_tokens: int
    timeout_seconds: int
    model: str | None = None  # None -> gateway resolves the configured default for the provider
    temperature: float | None = None
    structured_output: bool = False  # caller wants JSON-shaped output (enforced by caller's own schema, not the gateway)
    # e.g. {"organization_id": ..., "feature": "copilot"} -- for logging/metrics only, never sent to the provider
    metadata: dict = field(default_factory=dict)


@dataclass
class AIUsage:
    """Only ever populated from what the provider actually reports (Step 24:
    'Do NOT invent usage values when a provider does not return them')."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class AIGatewayResponse:
    text: str
    provider: str
    model: str
    usage: AIUsage
    finish_reason: str | None = None
    latency_seconds: float = 0.0
    request_id: str | None = None  # provider's own request/trace id, if it returns one
    metadata: dict = field(default_factory=dict)


# --- Normalized error taxonomy (Step 4) -------------------------------------
# Core RelayHub code (insights/ai/service.py, copilot/service.py) catches
# AIGatewayError broadly today (matching existing AIProviderError usage) but
# adapters raise the specific subclass so future callers, metrics, and the
# fallback policy (Step 19) can distinguish them without any `if provider ==`
# branching.


class AIGatewayError(Exception):
    """Base for every normalized gateway failure."""


class AIAuthenticationError(AIGatewayError):
    """Invalid/missing API key. Never triggers fallback (Step 19) -- retrying a
    bad key against a different provider doesn't make it valid."""


class AIRateLimitError(AIGatewayError):
    """Provider-side rate limit (HTTP 429 or vendor-specific equivalent)."""


class AITimeoutError(AIGatewayError):
    pass


class AIUnavailableError(AIGatewayError):
    """Provider unreachable / 5xx / network error."""


class AIInvalidRequestError(AIGatewayError):
    """Provider rejected the request as malformed (HTTP 400/422 or vendor
    equivalent). Never triggers fallback -- the same malformed request would
    fail against any provider."""


class AIContextLimitError(AIGatewayError):
    """Request exceeded the model's context window."""


class AIMalformedResponseError(AIGatewayError):
    """Provider returned a 2xx response that doesn't match its own documented
    response shape (missing fields, unexpected type). Distinct from the
    caller-side schema validation in insights/ai/schemas.py and
    copilot/schemas.py, which validates the *content* of a well-formed
    response against RelayHub's own JSON contract -- this is about the
    transport-level envelope being unparseable at all."""


class AIProviderError(AIGatewayError):
    """Catch-all for a provider-side failure that doesn't fit a more specific
    category above (e.g. an undocumented non-2xx status)."""


class AICapabilityError(AIGatewayError):
    """Raised by the gateway itself (not an adapter) when the resolved
    provider/model doesn't support a capability the request needs (Step 11).
    Never triggers fallback to the same provider/model -- but IS eligible to
    try the fallback provider if that provider's model supports it, since this
    reflects a model limitation, not a bad request."""


class AIUnknownProviderError(AIGatewayError):
    """Raised by the gateway when AI_PROVIDER (or a fallback) names a provider
    with no registered adapter."""
