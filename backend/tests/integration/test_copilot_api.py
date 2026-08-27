import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.modules.insights.ai.provider import FakeAIProvider
from tests.conftest import create_endpoint, register_and_get_token

pytestmark = pytest.mark.asyncio

NOW = datetime.now(timezone.utc)


async def _org_id(client, token: str) -> uuid.UUID:
    resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    return uuid.UUID(resp.json()["organization"]["id"])


async def _seed_incident(db_session, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID):
    from app.modules.insights.models import Incident, RootCauseAnalysis

    incident = Incident(
        organization_id=organization_id,
        endpoint_id=endpoint_id,
        status="open",
        failure_category="destination_5xx",
        severity="critical",
        title="Destination 5xx spike",
        summary="90% failure rate observed",
        opened_at=NOW - timedelta(minutes=30),
        last_signal_at=NOW,
    )
    db_session.add(incident)
    await db_session.flush()

    rca = RootCauseAnalysis(
        organization_id=organization_id,
        incident_id=incident.id,
        source="deterministic",
        likely_cause="Destination service is returning server errors (5xx).",
        confidence_level="highly_likely",
        confidence_score=0.85,
        evidence=[{"label": "5xx rate", "value": "85%"}],
        recommendations=["Check the destination service's health and recent deployments."],
    )
    db_session.add(rca)
    await db_session.commit()
    return incident.id


async def test_copilot_chat_requires_auth(client):
    resp = await client.post("/v1/insights/intelligence/copilot/chat", json={"message": "why is my endpoint failing?"})
    assert resp.status_code in (401, 403)


async def test_copilot_chat_returns_canned_response_when_ai_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER_ENABLED", False)
    token = await register_and_get_token(client, "copilot-disabled@example.com")

    resp = await client.post(
        "/v1/insights/intelligence/copilot/chat",
        json={"message": "why is my endpoint failing?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["grounded"] is False
    assert "not enabled" in body["answer"] or "isn't enabled" in body["answer"]
    assert body["citations"] == []


async def test_copilot_chat_sets_rate_limit_headers(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER_ENABLED", False)
    token = await register_and_get_token(client, "copilot-ratelimit@example.com")

    resp = await client.post(
        "/v1/insights/intelligence/copilot/chat",
        json={"message": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "X-RateLimit-Limit-Copilot" in resp.headers
    assert "X-RateLimit-Remaining-Copilot" in resp.headers


async def test_copilot_chat_success_grounds_answer_and_filters_hallucinated_citations(client, db_session, monkeypatch):
    from app.main import app
    from app.modules.insights.copilot.routes import _get_ai_provider_or_none

    monkeypatch.setattr(settings, "AI_PROVIDER_ENABLED", True)
    token = await register_and_get_token(client, "copilot-success@example.com")
    endpoint_id = await create_endpoint(client, token)
    org_id = await _org_id(client, token)
    incident_id = await _seed_incident(db_session, organization_id=org_id, endpoint_id=uuid.UUID(endpoint_id))

    fake_provider = FakeAIProvider()
    hallucinated_id = str(uuid.uuid4())
    fake_provider.queue_response(json.dumps({
        "answer": "Your endpoint is failing because the destination is returning 5xx errors.",
        "citations": [str(incident_id), hallucinated_id],
    }))
    app.dependency_overrides[_get_ai_provider_or_none] = lambda: fake_provider

    resp = await client.post(
        "/v1/insights/intelligence/copilot/chat",
        json={"message": "why is my endpoint failing?", "incident_id": str(incident_id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    del app.dependency_overrides[_get_ai_provider_or_none]

    assert resp.status_code == 200
    body = resp.json()
    assert body["grounded"] is True
    assert "5xx" in body["answer"]
    # Only the real incident ID survives -- the model-hallucinated one is dropped.
    cited_ids = [c["incident_id"] for c in body["citations"]]
    assert cited_ids == [str(incident_id)]
    assert len(fake_provider.calls) == 1


async def test_copilot_chat_fails_safe_on_malformed_ai_output(client, db_session, monkeypatch):
    from app.main import app
    from app.modules.insights.copilot.routes import _get_ai_provider_or_none

    monkeypatch.setattr(settings, "AI_PROVIDER_ENABLED", True)
    token = await register_and_get_token(client, "copilot-malformed@example.com")

    fake_provider = FakeAIProvider()
    fake_provider.queue_response("not valid json")
    app.dependency_overrides[_get_ai_provider_or_none] = lambda: fake_provider

    resp = await client.post(
        "/v1/insights/intelligence/copilot/chat",
        json={"message": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    del app.dependency_overrides[_get_ai_provider_or_none]

    assert resp.status_code == 200
    body = resp.json()
    assert body["grounded"] is False
    assert body["citations"] == []


async def test_copilot_chat_rejects_oversized_message(client, monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER_ENABLED", False)
    token = await register_and_get_token(client, "copilot-oversized@example.com")

    resp = await client.post(
        "/v1/insights/intelligence/copilot/chat",
        json={"message": "x" * 5000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
