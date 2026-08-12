# Webhook Developer Guide

Everything here describes behavior actually implemented in
`backend/app/modules/endpoints`, `events`, `delivery`, `dlq`, and
`common/notification_client.py`/signing code -- nothing aspirational.

## 1. Creating an endpoint

An endpoint is a URL plus delivery configuration: which event types it's
subscribed to, custom headers, timeout, retry limit, and an optional IP
allowlist. Create one via `POST /endpoints` (requires an `admin` session token,
not an API key):

```bash
curl -X POST https://api.relayhub.dev/v1/endpoints \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "Production webhook",
    "url": "https://api.example.com/webhooks/relayhub",
    "environment": "live",
    "subscribed_event_types": ["payment.success", "payment.failed"],
    "max_retry_attempts": 5
  }'
```

The response includes the endpoint's `id` -- you don't get the signing secret
here; see step 3.

## 2. Publishing an event

Publishing uses an **API key**, not a session token (`POST /events` requires the
`events:write` scope):

```bash
curl -X POST https://api.relayhub.dev/v1/events \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "event": "payment.success",
    "payload": {"order_id": "ord_123", "amount": 4200},
    "environment": "live",
    "idempotency_key": "ord_123-payment-success"
  }'
```

RelayHub fans this out to every active endpoint subscribed to `payment.success`
in the `live` environment. The response includes one `delivery_jobs` entry per
subscribed endpoint.

## 3. Endpoint authentication / signing

Every delivery is signed with HMAC-SHA256 using a secret unique to that
endpoint. Get the secret when you create the endpoint's first signing key or by
rotating it:

```bash
curl -X POST https://api.relayhub.dev/v1/endpoints/ep_abc123/rotate-secret \
  -H "Authorization: Bearer $TOKEN"
```

The response's `secret` field is shown once -- store it in your own secret
manager. `grace_period_hours` (optional) keeps the previous secret valid in
parallel during rotation, so you don't need perfectly-synchronized deploys on
both sides.

## 4. Verifying signatures

Each delivery includes a signature header computed the same way described in
the landing page's developer-experience section. Verify it before trusting the
payload:

```js
import { createHmac, timingSafeEqual } from "crypto";

function isValidSignature(rawBody, signatureHeader, secret) {
  const expected = createHmac("sha256", secret).update(rawBody).digest("hex");
  return timingSafeEqual(Buffer.from(signatureHeader), Buffer.from(expected));
}
```

Verify against the **raw request body bytes**, not a re-serialized version of
the parsed JSON -- re-serializing can change whitespace/key order and break
verification for reasons that are maddening to debug. See
`sdks/*/examples` for language-specific verification examples.

## 5. Delivery attempts

Every attempt -- success or failure -- is recorded with status, HTTP status
code, latency, and error category/message if applicable. Inspect the full
history for a job:

```bash
curl https://api.relayhub.dev/v1/deliveries/job_abc123 -H "Authorization: Bearer $TOKEN"
```

Or search across all deliveries with `GET /logs` (filterable by endpoint,
status, event type, environment, request ID, worker, date range, latency range
-- see `docs/api/deliveries.md`).

## 6. Retry behavior

A non-2xx response or a timeout schedules a retry on an exponential backoff
schedule, up to the endpoint's `max_retry_attempts`. You don't build retry logic
on your end -- RelayHub's Celery beat schedule (`check_due_retries`, every 10
seconds) finds due retries and re-enqueues them. Each attempt is logged
independently, so you can see exactly when and how many times a delivery was retried.

## 7. Replay

Once the retry budget is exhausted, a delivery moves to the dead-letter queue
(see below). Replay it manually once you've fixed whatever was rejecting it:

```bash
curl -X POST https://api.relayhub.dev/v1/dlq/dlj_xyz789/retry -H "Authorization: Bearer $TOKEN"
```

This is the *only* way to replay a delivery in the current API -- there's no
separate `/replay` endpoint, and it only applies to dead-lettered deliveries
(you can't "replay" a delivery that's still actively retrying or that already
succeeded).

## 8. DLQ

`GET /dlq` lists everything currently dead-lettered, with the full payload and
attempt/failure history retained. `POST /dlq/bulk-retry` replays up to 500 at
once. `DELETE /dlq/{id}` permanently discards one without replaying it.

## 9. Idempotency

`POST /events` accepts an `idempotency_key` field in the request body. If your
own system might retry a publish call (e.g. after a network timeout where you
don't know if the first request landed), generate a stable key per logical
event (e.g. `"{order_id}-payment-success"`) and pass it every time -- this is
the only idempotency mechanism implemented in the current API; there is no
idempotency support on any other endpoint.

## 10. Failure handling

- **Your endpoint returns a 4xx:** treated as a failure, retried on the normal
  backoff schedule like a 5xx. RelayHub doesn't distinguish "your fault" 4xx
  responses from transient 5xx ones -- if you need a request to *not* be
  retried, that's not currently configurable per-response.
- **Your endpoint times out:** counted as a failed attempt using the endpoint's
  configured `timeout_seconds`.
- **Your endpoint is permanently broken:** once `max_retry_attempts` is
  exhausted, the delivery dead-letters instead of retrying forever.

## 11. Security best practices

- Always verify the signature before processing a payload -- see step 4.
- Verify against the raw body, not a re-parsed/re-serialized one.
- Use a constant-time comparison (`timingSafeEqual` / `hmac.compare_digest`), not `==`.
- Rotate signing secrets periodically using the grace-period option so there's
  no delivery downtime.
- Set an IP allowlist on the endpoint if your receiving infrastructure can
  enforce it (`ip_allowlist` on `POST /endpoints`).
- Keep `BLOCK_PRIVATE_IP_TARGETS=true` in your RelayHub deployment (self-hosters
  only) -- it prevents endpoints from being pointed at internal/private IP
  ranges (SSRF protection).
