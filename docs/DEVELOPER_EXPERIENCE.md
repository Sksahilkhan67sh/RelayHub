# RelayHub Developer Experience

Map of the developer-facing tooling: what exists, where it lives, and — where
something was deliberately *not* built — why.

---

## Start here

| I want to… | Go to |
|---|---|
| Get running locally end-to-end | `docs/LOCAL_DEVELOPMENT.md` |
| Work out why a delivery failed | `docs/WEBHOOK_DEBUGGING.md` |
| Understand retry/DLQ semantics | `docs/RELIABILITY.md` |
| Call the API | `docs/api/` (one file per module) |
| Use an SDK | `docs/sdks/README.md`, `sdks/`, `examples/` |
| Use the CLI | `docs/cli/README.md`, `cli/` |
| Verify signatures in my language | `docs/webhooks/README.md`, `examples/` |
| Operate RelayHub in production | `docs/operations/` |

The marketing site also carries a developer section (`/developers`) with
quickstart, concepts, retries, replay, DLQ, SDKs, CLI, security, and
troubleshooting pages.

## Dashboard tooling

| Page | What it's for |
|---|---|
| **Events** | Browse and filter events; send a test event |
| **Deliveries** | Per-delivery attempt history: status, duration, error category, error message, destination IP, worker ID, next retry time |
| **Retry Queue** | Jobs currently awaiting retry |
| **Dead Letter Queue** | Inspect exhausted deliveries, replay them, export CSV |
| **Signature Inspector** | Verify a webhook signature, client-side |
| **Analytics / Intelligence** | Delivery metrics; anomaly and incident views |
| **Admin → Operations** | Queue depth, worker health, delivery metrics (platform admins) |

## Test events

`POST /v1/events/test` (dashboard session auth) exists so you can send a test
event from the UI without minting an API key and pasting it somewhere.

It calls exactly the same `service.publish_event` as `POST /v1/events` — real
fan-out, real signing, the real delivery queue, real retries, the real DLQ.
**There is no simulated delivery path.** The differences:

- authenticated by session rather than API key
- `api_key_id` is left null, which is what distinguishes dashboard test events
  from real API traffic afterwards
- rate limited to 30/min per organization

Because `enforce_event_publishing_limit` is API-key-scoped, it doesn't apply
here; the per-organization rate limit is what bounds this endpoint. At 30/min
that isn't a meaningful quota-evasion path, but it is a deliberate tradeoff
worth knowing about rather than discovering.

For programmatic traffic, use a real API key and `POST /v1/events`.

## Signature inspector

Dashboard → **Signature Inspector** (`/developer/signature-inspector`).

**The signing secret never leaves the browser.** Verification runs entirely
client-side via the Web Crypto API — nothing is sent to the API, stored, or
logged. This was a deliberate architectural choice: a server-side inspector
would mean transmitting a signing secret over the network to an endpoint that
must then be trusted never to log it. Client-side removes that risk class
instead of managing it.

Its logic was cross-verified against the backend implementation — the same
inputs produce byte-identical digests in both the browser-equivalent JS path
and `backend/app/modules/delivery/signing.py`. It is not a reimplementation
that might drift silently; the signing contract is also treated as frozen
(changing it would break every deployed customer verifier).

When verification fails it gives a specific reason — malformed signature,
non-integer timestamp, missing nonce, stale timestamp, or genuine mismatch —
and shows expected vs received signatures **truncated**, never the secret.

## On failure simulation

RelayHub deliberately does **not** ship a built-in failure simulator, despite
it being an obvious DX feature. The reasoning, since "we didn't build it" is
worth justifying:

A simulator needs a destination that returns arbitrary status codes on demand.
There are two ways to provide one, and both are bad here:

1. **Run one inside RelayHub** (e.g. a `/simulate/503` endpoint). RelayHub
   validates every webhook destination at connect time and blocks private,
   loopback, and metadata addresses to prevent SSRF. A self-hosted simulator
   destination would either be blocked by that same protection, or require
   punching a hole in it — and an SSRF allowlist entry that developer tooling
   can point at is exactly the kind of thing that becomes a bypass. Not worth
   it.
2. **Run a separate public service.** That's new infrastructure to deploy,
   secure, and pay for, to replicate something existing request-bin services
   already do well.

So: use an external request-bin style service that lets you choose the response
status, set `max_retry_attempts` low, and send a test event. You get genuine
retries and a genuine DLQ entry through the real pipeline — which is what a
simulator would have been for. `docs/LOCAL_DEVELOPMENT.md` steps 9–11 walk
through it.

If a first-party simulator is ever wanted, the safe shape is a separately
deployed public service with its own hostname — never a carve-out in the SSRF
validator.

## Realtime

Delivery status updates stream over SSE. The client uses explicit reconnect
with exponential backoff (1s → 30s cap, so an outage can't cause a reconnect
storm) and refetches from the REST API on every reconnect, since SSE delivery
isn't guaranteed. Realtime is a convenience layer — durable delivery state is
always in PostgreSQL, and a realtime failure can never corrupt it.

## Security posture of developer tooling

Every tool above is subject to the same controls as the rest of the API:

- **Tenant isolation** — enforced structurally via `tenant_select()` plus a
  build-time lint that fails CI on unscoped queries. Test events cannot target
  another organization's endpoints (regression-tested).
- **RBAC** — test events require `MEMBER`; DLQ replay requires `ADMIN`.
- **Rate limits** — test events 30/min, DLQ replay 60/min, bulk replay 10/min,
  DLQ export 10/min, all per organization.
- **SSRF** — unchanged and not weakened; see the simulator note above.
- **Secrets** — the signing secret is only ever handled client-side by the
  inspector; endpoint secrets are stored encrypted and never returned by the
  API after creation.

Details in `docs/operations/SECURITY.md`.

## Known gaps

- No first-party failure simulator (reasoned above).
- No request/response **body** capture on delivery attempts — the delivery
  debugger shows status, timing, error category, and error message, but not
  response bodies. Capturing them would mean storing customer response
  payloads, which is a privacy and storage-growth decision, not just a feature.
- Frontend has no automated test runner configured; frontend verification is
  TypeScript + ESLint + build only.
- The test-event quota note above (`enforce_event_publishing_limit` not
  applied).
