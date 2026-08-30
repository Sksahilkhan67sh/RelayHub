"""
Universal AI provider gateway (Phase: Universal AI Provider & Model Compatibility).

This package is the ONE place in RelayHub that knows about provider-specific APIs
(Anthropic, OpenAI, Gemini, xAI/Grok, ...). Nothing outside `ai_gateway/` and its
adapters should import an SDK or build a provider-specific HTTP request.

Callers (insights/ai/service.py, insights/copilot/service.py) go through
`get_gateway()` and speak only in `AIGatewayRequest` / `AIGatewayResponse` /
`AIGatewayError` — see contracts.py. `insights/ai/provider.py` keeps its
pre-existing narrow Protocol (`AIProvider.complete(request) -> str`) as a thin,
backward-compatible shim over this gateway so no existing call site changes.
"""

from app.modules.ai_gateway.gateway import AIGateway, get_gateway

__all__ = ["AIGateway", "get_gateway"]
