from __future__ import annotations

import httpx

from relayhub import RelayHubClient


def make_client(handler, **kwargs) -> RelayHubClient:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return RelayHubClient(api_key="test_key", http_client=http_client, max_retries=kwargs.pop("max_retries", 0), **kwargs)


def json_response(status: int, body) -> httpx.Response:
    return httpx.Response(status, json=body)


def test_health_hits_intelligence_path_not_bare_insights():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["query"] = dict(request.url.params)
        return json_response(200, [])

    client = make_client(handler)
    result = client.insights.health(endpoint_id="ep_1")

    # Regression guard: /v1/insights/... (bare) is already owned by the analytics
    # alias -- this resource must hit /v1/insights/intelligence/... or it would
    # silently collide with analytics summary/export routes.
    assert captured["path"] == "/v1/insights/intelligence/health"
    assert captured["query"]["endpoint_id"] == "ep_1"
    assert result == []


def test_health_history_builds_path_with_endpoint_id():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["query"] = dict(request.url.params)
        return json_response(200, [])

    client = make_client(handler)
    client.insights.health_history("ep_42", limit=10, offset=5)

    assert captured["path"] == "/v1/insights/intelligence/health/ep_42/history"
    assert captured["query"]["limit"] == "10"
    assert captured["query"]["offset"] == "5"


def test_anomalies_passes_all_filters_as_query_params():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["query"] = dict(request.url.params)
        return json_response(200, [])

    client = make_client(handler)
    client.insights.anomalies(endpoint_id="ep_1", metric="latency_p95", since="2026-01-01T00:00:00Z", limit=25, offset=0)

    assert captured["query"]["endpoint_id"] == "ep_1"
    assert captured["query"]["metric"] == "latency_p95"
    assert captured["query"]["since"] == "2026-01-01T00:00:00Z"
    assert captured["query"]["limit"] == "25"


def test_incidents_list_returns_typed_rows():
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(
            200,
            [
                {
                    "id": "inc_1",
                    "endpoint_id": "ep_1",
                    "status": "open",
                    "failure_category": "timeout",
                    "severity": "high",
                    "title": "Elevated timeouts",
                    "summary": "Timeout rate above baseline",
                    "opened_at": "2026-01-01T00:00:00Z",
                    "recovering_since": None,
                    "resolved_at": None,
                    "last_signal_at": "2026-01-01T00:05:00Z",
                }
            ],
        )

    client = make_client(handler)
    incidents = client.insights.incidents(status="open")
    assert incidents[0]["id"] == "inc_1"
    assert incidents[0]["status"] == "open"


def test_get_incident_hits_detail_path():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return json_response(
            200,
            {
                "id": "inc_1",
                "endpoint_id": None,
                "status": "resolved",
                "failure_category": "5xx",
                "severity": "medium",
                "title": "5xx spike",
                "summary": "summary",
                "opened_at": "2026-01-01T00:00:00Z",
                "recovering_since": None,
                "resolved_at": "2026-01-01T01:00:00Z",
                "last_signal_at": "2026-01-01T01:00:00Z",
                "anomalies": [],
                "rca_entries": [],
            },
        )

    client = make_client(handler)
    incident = client.insights.get_incident("inc_1")
    assert captured["path"] == "/v1/insights/intelligence/incidents/inc_1"
    assert incident["rca_entries"] == []


def test_incident_rca_keeps_deterministic_and_ai_sources_distinguishable():
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(
            200,
            [
                {
                    "id": "rca_1",
                    "source": "deterministic",
                    "likely_cause": "Endpoint returning 503s",
                    "confidence_level": "high",
                    "confidence_score": 0.9,
                    "evidence": [],
                    "recommendations": [],
                    "ai_provider": None,
                    "ai_model": None,
                    "created_at": "2026-01-01T00:00:00Z",
                },
                {
                    "id": "rca_2",
                    "source": "ai",
                    "likely_cause": "Possible downstream dependency outage",
                    "confidence_level": "medium",
                    "confidence_score": 0.6,
                    "evidence": [],
                    "recommendations": ["Check downstream status page"],
                    "ai_provider": "anthropic",
                    "ai_model": "claude",
                    "created_at": "2026-01-01T00:01:00Z",
                },
            ],
        )

    client = make_client(handler)
    entries = client.insights.incident_rca("inc_1")
    sources = {e["source"] for e in entries}
    assert sources == {"deterministic", "ai"}


def test_incident_recommendations_path_and_shape():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return json_response(200, {"incident_id": "inc_1", "recommendations": ["Increase timeout", "Add circuit breaker"]})

    client = make_client(handler)
    recs = client.insights.incident_recommendations("inc_1")
    assert captured["path"] == "/v1/insights/intelligence/incidents/inc_1/recommendations"
    assert recs["recommendations"] == ["Increase timeout", "Add circuit breaker"]


def test_incident_timeline_path_and_shape():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return json_response(
            200,
            {"incident_id": "inc_1", "status": "open", "events": [{"type": "anomaly_detected", "at": "2026-01-01T00:00:00Z", "detail": "d"}]},
        )

    client = make_client(handler)
    timeline = client.insights.incident_timeline("inc_1")
    assert captured["path"] == "/v1/insights/intelligence/incidents/inc_1/timeline"
    assert timeline["events"][0]["type"] == "anomaly_detected"
