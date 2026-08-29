# Real-time delivery status

RelayHub's dashboard receives live updates when a delivery job changes state
(`queued` → `processing` → `success`/`failed`/`retrying`/`dead_letter`), without
a manual page refresh. This is a **notification transport only** — PostgreSQL's
`delivery_jobs`/`delivery_attempts` tables remain the sole source of truth for
delivery state, exactly as before this feature existed.

## Architecture

```
Existing delivery worker / service (unchanged)
        |
        v
   DB commit (delivery_jobs.status = ...)
        |
        v
emit_delivery_update()  <- failure-isolated, never raises
        |
        v
Redis pub/sub, channel: relayhub:realtime:org:{organization_id}
        |
        v
FastAPI SSE endpoint: GET /v1/realtime/deliveries/stream
        |
        v
Browser EventSource (apps/web/lib/realtime.ts)
        |
        v
Live UI update (no refresh)
```

Nothing about the existing delivery/retry/DLQ architecture changed. This phase
only adds: a publish call after four existing commit points, one new SSE route,
and a frontend hook.

## Connection setup

`GET /v1/realtime/deliveries/stream?token=<access_token>`

Browser `EventSource` cannot set an `Authorization` header, so the same
short-lived access token used everywhere else in the app is passed as a query
parameter. Non-browser callers (curl, the CLI, server-to-server tooling) may
instead send a normal `Authorization: Bearer <token>` header — the endpoint
accepts either, decoding with the exact same `decode_token` verification path
`get_current_auth` uses for every other route.

## Event schema

Every message is an SSE frame:

```
event: delivery.updated
data: {"type":"delivery.updated","delivery_job_id":"...", ...}
```

```json
{
  "type": "delivery.updated",
  "delivery_job_id": "<uuid>",
  "event_id": "<uuid>",
  "endpoint_id": "<uuid>",
  "organization_id": "<uuid>",
  "status": "queued | processing | success | retrying | failed | dead_letter",
  "attempt_number": 0,
  "max_attempts": 5,
  "http_status": 200,
  "error_category": null,
  "queued_at": "2026-08-29T12:00:00+00:00",
  "next_attempt_at": null,
  "completed_at": "2026-08-29T12:00:01+00:00",
  "timestamp": "2026-08-29T12:00:01.123456+00:00"
}
```

Field names and every possible `status` value match
`app.modules.delivery.models.DeliveryJobStatus` exactly. See
`backend/app/modules/realtime/events.py` for the authoritative contract
docstring.

## Authentication & tenant isolation

- The connection's `organization_id` comes **only** from the decoded,
  signature-verified JWT — never from a client-supplied parameter.
- A connection subscribes to exactly one Redis channel:
  `relayhub:realtime:org:{organization_id}`, derived server-side from that same
  claim. There is no code path by which a connection can name a different
  organization's channel.
- Minimum role: `viewer` (same as `GET /v1/deliveries/{id}`) — anyone who can
  read delivery state over REST can watch it live; nobody else.
- Verified in `backend/tests/integration/test_realtime_stream.py` at the
  transport level (two real organizations, two real streams, asserting org A's
  stream never receives anything published for org B) — not just visually.

## Reconnection & missed-event reconciliation

`apps/web/lib/realtime.ts`'s `useDeliveryRealtimeStream` hook:

- Opens a fresh `EventSource` rather than relying on the browser's built-in
  auto-retry, because access tokens rotate every 15 minutes and the token is
  embedded in the connection URL — the built-in retry would keep reusing an
  increasingly stale token forever after the first rotation.
- Reconnects with exponential backoff (1s, 2s, 4s, ... capped at 30s) on any
  drop: network blip, server restart, Redis restart, or a rejected/expired
  token.
- Fires an `onReconciliationNeeded` callback on every successful (re)connect,
  including the first one. The pages using the hook respond by refetching the
  authoritative REST state (`GET /v1/logs`, `GET /v1/deliveries/{id}`) — since
  SSE delivery isn't guaranteed, this is what makes a missed event during any
  gap self-heal instead of leaving the UI stale.

## Failure isolation

`emit_delivery_update` (`backend/app/modules/realtime/events.py`) never raises.
Any publish failure (Redis down, network blip) is logged and swallowed. This is
enforced by design, not just convention: every call site invokes it strictly
**after** its own `db.commit()`, so a realtime failure can never turn an
already-durably-persisted delivery state change into a failed request or a
failed Celery task. Verified in
`backend/tests/unit/test_realtime_publisher.py::test_emit_delivery_update_never_raises_when_publisher_fails`.

## Frontend fallback

The delivery detail page (`apps/web/app/(dashboard)/deliveries/[id]/page.tsx`)
keeps its original 5-second polling loop, but only as a fallback: it now runs
**only** while the job is non-terminal **and** the realtime connection is not
currently `live`/`connecting`. While the SSE stream is healthy, polling is
fully idle. This means a Redis or SSE outage degrades gracefully to the
pre-this-phase polling behavior rather than the page going silent.

## Local development

No new environment variables. The realtime publisher reuses `settings.REDIS_URL`
(the same Redis DB `app/core/health.py`'s readiness probe already pings),
distinct from the Celery broker/result-backend Redis DBs. If Redis is
unreachable in local dev, delivery itself is unaffected — the dashboard simply
won't receive live updates until the fallback poll or a manual refresh happens.

## Production considerations

- One Redis pub/sub channel per organization bounds fan-out (`Step 4/18`): a
  publish reaches only that organization's currently-connected streams, never
  a global broadcast.
- `relayhub_realtime_connections` (gauge), `relayhub_realtime_events_published_total`
  (counter, labeled by status), `relayhub_realtime_publish_failures_total`, and
  `relayhub_realtime_reconnects_total` are exposed via the existing
  `/metrics` Prometheus endpoint. `realtime_events_published_total` is
  incremented from both the API process (event publish, DLQ replay) and the
  Celery worker process (executor, reconciliation) — see the comment in
  `backend/app/core/metrics.py` for the same documented per-process-visibility
  caveat this codebase already applies to its AI call metrics.
- No secrets are logged by any realtime code path.
