"""
Gateway-level test double (Step 34's "mocked provider APIs for deterministic
unit tests", one level up from adapter-level httpx mocking). Same
queue-a-response-or-an-exception shape as the pre-existing
insights.ai.provider.FakeAIProvider, so gateway/adapter-selection/fallback
tests read the same way the existing AI test suite already does.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.modules.ai_gateway.contracts import AIGatewayError, AIGatewayRequest, AIGatewayResponse, AIUsage


@dataclass
class FakeAdapter:
    provider_name: str = "fake"
    model: str = "fake-model"
    queued_responses: list[str] = field(default_factory=list)
    queued_exception: Exception | None = None
    calls: list[AIGatewayRequest] = field(default_factory=list)
    latency_seconds: float = 0.0

    async def health_check(self) -> bool:
        return True

    async def complete(self, request: AIGatewayRequest) -> AIGatewayResponse:
        self.calls.append(request)
        if self.latency_seconds:
            await asyncio.sleep(self.latency_seconds)
        if self.queued_exception is not None:
            raise self.queued_exception
        if not self.queued_responses:
            raise AIGatewayError("FakeAdapter: no queued response -- call queue_response() first in the test")
        text = self.queued_responses.pop(0)
        return AIGatewayResponse(
            text=text,
            provider=self.provider_name,
            model=request.model or self.model,
            usage=AIUsage(),
        )

    def queue_response(self, raw_text: str) -> None:
        self.queued_responses.append(raw_text)

    def queue_failure(self, exc: Exception) -> None:
        self.queued_exception = exc
