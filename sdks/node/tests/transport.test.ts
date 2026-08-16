import { test } from "node:test";
import assert from "node:assert/strict";
import { RelayHubClient } from "../src/client.js";
import { RelayHubNotFoundError, RelayHubRateLimitError, RelayHubValidationError } from "../src/errors.js";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

test("sends X-RelayHub-Api-Key, matching the backend's actual API-key auth dependency", async () => {
  let capturedHeaders: Headers | undefined;
  const fakeFetch: typeof fetch = async (_url, init) => {
    capturedHeaders = new Headers(init?.headers);
    return jsonResponse(200, { id: "ep_123", name: "Test" });
  };
  const client = new RelayHubClient({ apiKey: "test_key_abc", fetch: fakeFetch, maxRetries: 0 });
  await client.endpoints.get("ep_123");

  assert.equal(capturedHeaders?.get("x-relayhub-api-key"), "test_key_abc");
  // Regression guard: this transport previously sent Authorization: Bearer instead,
  // which the backend's API-key dependency never reads -- every real request 401'd.
  assert.equal(capturedHeaders?.get("authorization"), null);
});

test("successful GET returns parsed JSON", async () => {
  const fakeFetch: typeof fetch = async () => jsonResponse(200, { id: "ep_123", name: "Test" });
  const client = new RelayHubClient({ apiKey: "test_key", fetch: fakeFetch, maxRetries: 0 });
  const endpoint = await client.endpoints.get("ep_123");
  assert.equal(endpoint.name, "Test");
});

test("404 maps to RelayHubNotFoundError with the server's message", async () => {
  const fakeFetch: typeof fetch = async () => jsonResponse(404, { error: { message: "Endpoint not found", code: "not_found" } });
  const client = new RelayHubClient({ apiKey: "test_key", fetch: fakeFetch, maxRetries: 0 });
  await assert.rejects(() => client.endpoints.get("missing"), (err: unknown) => {
    assert.ok(err instanceof RelayHubNotFoundError);
    if (err instanceof RelayHubNotFoundError) {
      assert.equal(err.message, "Endpoint not found");
      assert.equal(err.status, 404);
    }
    return true;
  });
});

test("422 maps to RelayHubValidationError", async () => {
  const fakeFetch: typeof fetch = async () => jsonResponse(422, { error: { message: "Invalid event type" } });
  const client = new RelayHubClient({ apiKey: "test_key", fetch: fakeFetch, maxRetries: 0 });
  await assert.rejects(() => client.events.publish({ event: "bad" }), RelayHubValidationError);
});

test("429 is retried up to maxRetries, then raises RelayHubRateLimitError", async () => {
  let calls = 0;
  const fakeFetch: typeof fetch = async () => {
    calls++;
    return jsonResponse(429, { error: { message: "Too many requests" } }, { "retry-after": "0" });
  };
  const client = new RelayHubClient({ apiKey: "test_key", fetch: fakeFetch, maxRetries: 2 });
  await assert.rejects(() => client.endpoints.list(), RelayHubRateLimitError);
  assert.equal(calls, 3); // initial attempt + 2 retries
});

test("a request that eventually succeeds after a 500 does not throw", async () => {
  let calls = 0;
  const fakeFetch: typeof fetch = async () => {
    calls++;
    if (calls === 1) return jsonResponse(500, { error: { message: "boom" } });
    return jsonResponse(200, []);
  };
  const client = new RelayHubClient({ apiKey: "test_key", fetch: fakeFetch, maxRetries: 2 });
  const result = await client.endpoints.list();
  assert.deepEqual(result, []);
  assert.equal(calls, 2);
});

test("204 responses resolve to undefined without attempting to parse a body", async () => {
  const fakeFetch: typeof fetch = async () => new Response(null, { status: 204 });
  const client = new RelayHubClient({ apiKey: "test_key", fetch: fakeFetch, maxRetries: 0 });
  const result = await client.auth.logout();
  assert.equal(result, undefined);
});

test("idempotencyKey option sets idempotency_key on the request body", async () => {
  let capturedBody: unknown;
  const fakeFetch: typeof fetch = async (_url, init) => {
    capturedBody = JSON.parse(String(init?.body));
    return jsonResponse(201, { id: "evt_1", event: "payment.success", environment: "test", payload: {}, request_id: "req_1", created_at: "now", delivery_jobs: [] });
  };
  const client = new RelayHubClient({ apiKey: "test_key", fetch: fakeFetch, maxRetries: 0 });
  await client.events.publish({ event: "payment.success" }, { idempotencyKey: "order-42" });
  assert.equal((capturedBody as Record<string, unknown>).idempotency_key, "order-42");
});

test("builder pattern produces an equivalent client to the constructor", async () => {
  const fakeFetch: typeof fetch = async () => jsonResponse(200, { user: {}, organization: {}, role: "member" });
  const client = RelayHubClient.builder().apiKey("test_key").fetchImpl(fakeFetch).maxRetries(0).build();
  const me = await client.auth.me();
  assert.equal(me.role, "member");
});

test("builder requires an apiKey before build()", () => {
  assert.throws(() => RelayHubClient.builder().build(), /apiKey/);
});
