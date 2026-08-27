import { test } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { insightsCommand } from "../src/commands/insights.js";
import { parseArgs } from "../src/args.js";

// Minimal local HTTP server, same approach the Node SDK's own tests use --
// no mocking framework, real request/response round trip.
function startServer(handler: (req: http.IncomingMessage, res: http.ServerResponse) => void): Promise<{ url: string; close: () => Promise<void> }> {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      resolve({
        url: `http://127.0.0.1:${port}`,
        close: () => new Promise((res) => server.close(() => res())),
      });
    });
  });
}

function captureStdout(): { output: string[]; restore: () => void } {
  const output: string[] = [];
  const original = console.log;
  console.log = (...args: unknown[]) => output.push(args.map(String).join(" "));
  return { output, restore: () => (console.log = original) };
}

test("insights health command hits /v1/insights/intelligence/health and prints a table", async () => {
  let capturedPath: string | undefined;
  const { url, close } = await startServer((req, res) => {
    capturedPath = req.url?.split("?")[0];
    res.writeHead(200, { "content-type": "application/json" });
    res.end(
      JSON.stringify([
        { endpoint_id: "ep_1", status: "healthy", health_score: 0.95, confidence: 0.9, sample_size: 100 },
      ])
    );
  });

  const capture = captureStdout();
  try {
    await insightsCommand(parseArgs(["health", "--api-key", "test_key", "--base-url", url]));
  } finally {
    capture.restore();
    await close();
  }

  // Regression guard: must not hit bare /v1/insights (owned by the analytics alias).
  assert.equal(capturedPath, "/v1/insights/intelligence/health");
  assert.ok(capture.output.some((line) => line.includes("ep_1")));
});

test("insights incident command prints anomalies and RCA with source labels", async () => {
  const { url, close } = await startServer((req, res) => {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(
      JSON.stringify({
        id: "inc_1",
        status: "open",
        severity: "high",
        title: "Elevated timeouts",
        summary: "summary",
        endpoint_id: "ep_1",
        opened_at: "2026-01-01T00:00:00Z",
        recovering_since: null,
        resolved_at: null,
        last_signal_at: "2026-01-01T00:05:00Z",
        anomalies: [
          {
            id: "an_1",
            endpoint_id: "ep_1",
            metric: "timeout_rate",
            direction: "up",
            observed_value: 0.4,
            baseline_value: 0.05,
            delta: 0.35,
            observed_at: "2026-01-01T00:00:00Z",
            confidence: 0.85,
            sample_size: 50,
            evidence: [],
            incident_id: "inc_1",
          },
        ],
        rca_entries: [
          {
            id: "rca_1",
            source: "ai",
            likely_cause: "Possible downstream outage",
            confidence_level: "medium",
            confidence_score: 0.6,
            evidence: [],
            recommendations: [],
            ai_provider: "anthropic",
            ai_model: "claude",
            created_at: "2026-01-01T00:01:00Z",
          },
        ],
      })
    );
  });

  const capture = captureStdout();
  try {
    await insightsCommand(parseArgs(["incident", "inc_1", "--api-key", "test_key", "--base-url", url]));
  } finally {
    capture.restore();
    await close();
  }

  const joined = capture.output.join("\n");
  // FACT (anomalies) vs INFERENCE (AI RCA) must stay visibly distinguished in CLI output.
  assert.ok(joined.includes("Anomalies (measured)"));
  assert.ok(joined.includes("AI inference"));
});

test("insights command with no positional defaults to the health view", async () => {
  let capturedPath: string | undefined;
  const { url, close } = await startServer((req, res) => {
    capturedPath = req.url?.split("?")[0];
    res.writeHead(200, { "content-type": "application/json" });
    res.end("[]");
  });

  const capture = captureStdout();
  try {
    await insightsCommand(parseArgs(["--api-key", "test_key", "--base-url", url]));
  } finally {
    capture.restore();
    await close();
  }

  assert.equal(capturedPath, "/v1/insights/intelligence/health");
});
