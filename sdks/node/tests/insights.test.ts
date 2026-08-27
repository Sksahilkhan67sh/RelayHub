import { test } from "node:test";
import assert from "node:assert/strict";
import { RelayHubClient } from "../src/client.js";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

function makeClient(fakeFetch: typeof fetch): RelayHubClient {
  return new RelayHubClient({ apiKey: "test_key", fetch: fakeFetch, maxRetries: 0 });
}

test("insights.health hits /v1/insights/intelligence/health, not bare /v1/insights", async () => {
  let capturedUrl: string | undefined;
  const fakeFetch: typeof fetch = async (url) => {
    capturedUrl = url.toString();
    return jsonResponse(200, []);
  };
  const client = makeClient(fakeFetch);
  const result = await client.insights.health({ endpoint_id: "ep_1" });

  // Regression guard: /v1/insights/... (bare) is already owned by the analytics
  // alias -- this resource must hit /v1/insights/intelligence/... or it would
  // silently collide with analytics summary/export routes.
  const parsed = new URL(capturedUrl!);
  assert.equal(parsed.pathname, "/v1/insights/intelligence/health");
  assert.equal(parsed.searchParams.get("endpoint_id"), "ep_1");
  assert.deepEqual(result, []);
});

test("insights.healthHistory builds path with endpointId", async () => {
  let capturedUrl: string | undefined;
  const fakeFetch: typeof fetch = async (url) => {
    capturedUrl = url.toString();
    return jsonResponse(200, []);
  };
  const client = makeClient(fakeFetch);
  await client.insights.healthHistory("ep_42", { limit: 10, offset: 5 });

  const parsed = new URL(capturedUrl!);
  assert.equal(parsed.pathname, "/v1/insights/intelligence/health/ep_42/history");
  assert.equal(parsed.searchParams.get("limit"), "10");
  assert.equal(parsed.searchParams.get("offset"), "5");
});

test("insights.anomalies passes all filters as query params", async () => {
  let capturedUrl: string | undefined;
  const fakeFetch: typeof fetch = async (url) => {
    capturedUrl = url.toString();
    return jsonResponse(200, []);
  };
  const client = makeClient(fakeFetch);
  await client.insights.anomalies({ endpoint_id: "ep_1", metric: "latency_p95", since: "2026-01-01T00:00:00Z", limit: 25 });

  const parsed = new URL(capturedUrl!);
  assert.equal(parsed.searchParams.get("endpoint_id"), "ep_1");
  assert.equal(parsed.searchParams.get("metric"), "latency_p95");
  assert.equal(parsed.searchParams.get("since"), "2026-01-01T00:00:00Z");
  assert.equal(parsed.searchParams.get("limit"), "25");
});

test("insights.getIncident hits detail path", async () => {
  let capturedUrl: string | undefined;
  const fakeFetch: typeof fetch = async (url) => {
    capturedUrl = url.toString();
    return jsonResponse(200, {
      id: "inc_1",
      endpoint_id: null,
      status: "resolved",
      failure_category: "5xx",
      severity: "medium",
      title: "5xx spike",
      summary: "summary",
      opened_at: "2026-01-01T00:00:00Z",
      recovering_since: null,
      resolved_at: "2026-01-01T01:00:00Z",
      last_signal_at: "2026-01-01T01:00:00Z",
      anomalies: [],
      rca_entries: [],
    });
  };
  const client = makeClient(fakeFetch);
  const incident = await client.insights.getIncident("inc_1");

  assert.equal(new URL(capturedUrl!).pathname, "/v1/insights/intelligence/incidents/inc_1");
  assert.deepEqual(incident.rca_entries, []);
});

test("insights.incidentRca keeps deterministic and ai sources distinguishable", async () => {
  const fakeFetch: typeof fetch = async () =>
    jsonResponse(200, [
      {
        id: "rca_1",
        source: "deterministic",
        likely_cause: "Endpoint returning 503s",
        confidence_level: "high",
        confidence_score: 0.9,
        evidence: [],
        recommendations: [],
        ai_provider: null,
        ai_model: null,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "rca_2",
        source: "ai",
        likely_cause: "Possible downstream dependency outage",
        confidence_level: "medium",
        confidence_score: 0.6,
        evidence: [],
        recommendations: ["Check downstream status page"],
        ai_provider: "anthropic",
        ai_model: "claude",
        created_at: "2026-01-01T00:01:00Z",
      },
    ]);
  const client = makeClient(fakeFetch);
  const entries = await client.insights.incidentRca("inc_1");

  const sources = new Set(entries.map((e) => e.source));
  assert.deepEqual(sources, new Set(["deterministic", "ai"]));
});

test("insights.incidentRecommendations path and shape", async () => {
  let capturedUrl: string | undefined;
  const fakeFetch: typeof fetch = async (url) => {
    capturedUrl = url.toString();
    return jsonResponse(200, { incident_id: "inc_1", recommendations: ["Increase timeout", "Add circuit breaker"] });
  };
  const client = makeClient(fakeFetch);
  const recs = await client.insights.incidentRecommendations("inc_1");

  assert.equal(new URL(capturedUrl!).pathname, "/v1/insights/intelligence/incidents/inc_1/recommendations");
  assert.deepEqual(recs.recommendations, ["Increase timeout", "Add circuit breaker"]);
});

test("insights.incidentTimeline path and shape", async () => {
  let capturedUrl: string | undefined;
  const fakeFetch: typeof fetch = async (url) => {
    capturedUrl = url.toString();
    return jsonResponse(200, {
      incident_id: "inc_1",
      status: "open",
      events: [{ type: "anomaly_detected", at: "2026-01-01T00:00:00Z", detail: "d" }],
    });
  };
  const client = makeClient(fakeFetch);
  const timeline = await client.insights.incidentTimeline("inc_1");

  assert.equal(new URL(capturedUrl!).pathname, "/v1/insights/intelligence/incidents/inc_1/timeline");
  assert.equal(timeline.events[0]!.type, "anomaly_detected");
});
