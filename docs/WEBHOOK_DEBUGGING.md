# Debugging Webhooks with RelayHub

Practical guide for working out *why* a delivery did what it did. Everything
here refers to features that actually exist in this repository — no aspirational
tooling.

---

## Verifying a signature

### The contract

RelayHub signs every delivery. Source of truth:
`backend/app/modules/delivery/signing.py`.

```
signed_string = "<timestamp>.<nonce>." + raw_body      (bytes)
signature     = hex(HMAC_SHA256(secret, signed_string))
```

Headers sent with every delivery:

| Header | Meaning |
|---|---|
| `X-RelayHub-Signature` | 64-char lowercase hex HMAC-SHA256 digest |
| `X-RelayHub-Timestamp` | Unix seconds, integer, as a string |
| `X-RelayHub-Nonce` | Random per-delivery value |
| `X-RelayHub-Event` | Event type, e.g. `payment.success` |
| `X-RelayHub-Delivery-ID` | The delivery job UUID, for your own dedup |

The timestamp and nonce are inside the signed string on purpose. If only the
body were signed, anyone who captured one valid request could replay it forever
with a fresh timestamp and the signature would still verify.

### The Signature Inspector

Dashboard → **Signature Inspector** (`/developer/signature-inspector`).

Paste the secret, timestamp, nonce, signature, and raw body; it tells you
whether they match and — when they don't — *why*.

**Your secret never leaves your browser.** The tool runs entirely client-side
using the Web Crypto API. Nothing is sent to the RelayHub API, stored, or
logged. Its logic is verified to produce byte-identical digests to the backend
implementation above.

### Why signatures usually fail

In rough order of how often it actually happens:

1. **The body was re-serialized before verifying.** This is the overwhelming
   favourite. RelayHub signs the exact bytes it sent. If your framework parsed
   the JSON into an object and you re-encoded it to verify, key order and
   whitespace may differ and the digest changes. Capture the *raw* body before
   any JSON parsing.
2. **Wrong or rotated secret.** Endpoints support secret rotation with a grace
   period (`endpoint_secrets.grace_period_ends_at`); during rotation, two
   secrets are valid. Make sure you're verifying against the right one.
3. **`sha256=` prefix.** Some platforms prefix the digest. RelayHub does not —
   send and compare the bare hex digest.
4. **Only the body was signed.** The signed string includes the timestamp and
   nonce; see the contract above.
5. **Stale timestamp.** A signature can be cryptographically valid but old.
   Reject anything outside a tolerance window (RelayHub's reference
   implementation uses 300s) as a replay.

### Compare in constant time

Use `hmac.compare_digest` (Python) or `crypto.timingSafeEqual` (Node). Never
`==`, which short-circuits and leaks timing information.

---

## Debugging a delivery

Dashboard → **Deliveries** → click any delivery.

The delivery detail page already surfaces the full attempt history: attempt
number, HTTP status, duration, error category, error message, destination IP,
worker ID, start time, and next retry time. That's usually enough to classify a
failure without touching the database.

### Reading `error_category`

This is the field that tells you whether RelayHub considered the failure your
destination's fault, a transient network problem, or RelayHub's own:

| Category | Meaning | Retryable |
|---|---|---|
| `none` | Success | — |
| `transient_http_error` | 408, 429, or 5xx from your endpoint | Yes |
| `permanent_http_error` | Other 4xx — your endpoint rejected it deliberately | No |
| `timeout` | Destination didn't respond within `timeout_seconds` | Yes |
| `connection_error` | TCP/DNS/TLS failure reaching the destination | Yes |
| `ssrf_blocked` | Destination resolved to a private/loopback/metadata address | No |
| `signing_error` | RelayHub could not sign the request | No |

Source of truth: `backend/app/modules/delivery/executor.py`.

### Retry behaviour

A retryable failure schedules the next attempt with exponential backoff plus
jitter, up to the endpoint's `max_retry_attempts`. When attempts are exhausted,
the job moves to `dead_letter` — the event, the delivery job, and **every**
attempt record are preserved. Nothing is deleted.

A non-retryable failure (`permanent_http_error`, `ssrf_blocked`,
`signing_error`) goes terminal immediately — retrying a 401 or a 422 just
generates load without changing the outcome.

Full lifecycle detail: `docs/RELIABILITY.md`.

### Replaying from the DLQ

Dashboard → **Dead Letter Queue** → inspect → retry. Or
`POST /v1/dlq/{id}/retry`.

Replay re-queues the **same** job with its **original** signed payload — it
doesn't create a new logical event, so idempotency and audit history stay
intact. Requires the `ADMIN` role, is tenant-scoped, and is rate limited
(60/min single, 10/min bulk, per organization).

**One caveat worth knowing**: replay resets `attempt_number` to 0 to give the
job a fresh retry budget. That means a replayed job can have two attempt rows
sharing the same `attempt_number`. Nothing is lost — order by `started_at`, not
`attempt_number`, when reconstructing a timeline. See `docs/RELIABILITY.md`.

---

## Sending a test event

Dashboard → **Events**, or `POST /v1/events/test` (session-authenticated).

This goes through the *real* pipeline: real fan-out, real signing, the real
delivery queue, real retries, the real DLQ. It is not a simulated path. The only
differences from `POST /v1/events` are that it authenticates with your dashboard
session instead of an API key, and it leaves `api_key_id` null — which is how
you tell dashboard-originated test events apart from real API traffic afterwards.

Rate limited to 30/min per organization. For programmatic traffic, use a real
API key and `POST /v1/events`.

---

## Simulating failures

RelayHub deliberately does **not** ship a built-in failure simulator. See
`docs/DEVELOPER_EXPERIENCE.md` ("On failure simulation") for the reasoning —
short version: doing it safely would mean either running a new public service
or weakening the SSRF protection that blocks private addresses, and neither is
worth it when external request-bin services already do the job.

To exercise retry and DLQ behaviour, point an endpoint at a service that lets
you choose the response status (for example a request-bin style tool), set
`max_retry_attempts` low, and send a test event. You'll get genuine retries and
a genuine DLQ entry through the real pipeline.

---

## Finding things

- **Deliveries** — filter by status, endpoint, and time range.
- **Events** — filter by type, ID, and time range.
- **Dead Letter Queue** — filter by endpoint; CSV export available (rate
  limited to 10/min per organization).

All list endpoints are paginated with bounded page sizes — there is no unbounded
query available through the API.

---

## Related documentation

- `docs/RELIABILITY.md` — delivery, retry, and DLQ semantics in depth
- `docs/LOCAL_DEVELOPMENT.md` — end-to-end local workflow
- `docs/operations/OBSERVABILITY.md` — metrics, logs, tracing (operators)
- `docs/api/` — per-module API reference
