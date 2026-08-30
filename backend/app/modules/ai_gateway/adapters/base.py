"""
The ONE interface every provider adapter implements (Step 1). The gateway
(gateway.py) only ever calls `complete()` and `health_check()` -- it never
constructs a provider-specific request object or inspects a provider-specific
response.
"""

from __future__ import annotations

from typing import Protocol

from app.modules.ai_gateway.contracts import AIGatewayRequest, AIGatewayResponse


class ProviderAdapter(Protocol):
    provider_name: str
    model: str

    async def complete(self, request: AIGatewayRequest) -> AIGatewayResponse:
        """Sends the request to this provider and returns a normalized
        response, or raises one of the AIGatewayError subclasses from
        contracts.py. Must never raise anything else -- adapters are
        responsible for mapping every vendor-specific failure mode
        (network error, timeout, 401/403/429/4xx/5xx, malformed body) into
        the normalized taxonomy so the gateway and callers never need
        provider-specific except clauses."""
        ...

    async def health_check(self) -> bool:
        """Lightweight/config-only check (Step 26: 'Do not perform expensive
        AI requests just to display health'). Returns True if this adapter is
        configured well enough to attempt a real call (has credentials, has a
        model configured) -- never makes a real API call itself."""
        ...
