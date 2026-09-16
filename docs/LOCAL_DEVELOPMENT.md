# Local Development Walkthrough

An end-to-end loop: start RelayHub locally, send an event, watch it deliver,
force a failure, watch it retry, replay it from the DLQ, and confirm success.

This complements the setup instructions in `README.md` — it doesn't repeat
them. Read the "Local development" section there first for install/run
commands.

---

## 0. Prerequisites

Running the **test suite** needs nothing but Python — it uses in-memory SQLite
(`backend/tests/conftest.py`). Running the **application** needs PostgreSQL and
Redis; `infra/docker/docker-compose.yml` provides both.

## 1. Start the stack

```bash
cp backend/.env.example backend/.env       # fill in real local values
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload              # API on :8000
```

In a second terminal, the worker and scheduler (delivery happens in Celery, not
in the request path — without these, events are created but never delivered):

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info    # retries + reconciliation
```

In a third, the frontend:

```bash
cp apps/web/.env.example apps/web/.env.local
cd apps/web && npm install && npm run dev   # UI on :3000
```

Sanity check: `curl localhost:8000/health/ready` should return `200` with both
`database` and `redis` reporting OK. If it returns `503`, one of those two isn't
up — the response body says which.

## 2. Create an account and organization

Register through the UI at `localhost:3000/register`. An organization is created
for you automatically, with your user as `OWNER`.

## 3. Set up a destination you control

You need somewhere for webhooks to actually land. Options:

- **A request-bin service** (a hosted URL that captures requests and lets you
  choose the response status). Easiest for exercising failure paths.
- **A local receiver** — see `examples/` in this repository, which includes a
  runnable webhook receiver and a signature-verification example.

⚠️ **A purely local receiver (`localhost`, `127.0.0.1`, a private LAN address)
will be rejected.** This is not a bug. RelayHub validates destinations at
connect time and blocks private, loopback, link-local, and cloud-metadata
addresses to prevent SSRF — see `docs/operations/SECURITY.md`. For local
development, use a public request-bin URL, or a tunnel that gives your local
receiver a public hostname.

## 4. Create an endpoint

Dashboard → **Endpoints** → create. Set the URL from step 3, subscribe it to an
event type (e.g. `order.created`), and **copy the signing secret — it is shown
once and never again** (it's stored encrypted and never returned by the API
afterwards).

Set `max_retry_attempts` to something small like `2` while you're experimenting,
so exhaustion and DLQ entry happen in seconds rather than many minutes of
backoff.

## 5. Send a test event

Dashboard → **Events**, or:

```bash
curl -X POST localhost:8000/v1/events/test \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event":"order.created","payload":{"order_id":"test_123"}}'
```

Event types must match `namespace.name` — lowercase, exactly one dot
(`order.created` ✓, `Order.Created` ✗, `a.b.c` ✗).

This goes through the real pipeline — real signing, real queue, real retries,
real DLQ. It is not a simulated path.

## 6. Inspect the request that arrived

At your destination, look at the headers: `X-RelayHub-Signature`,
`-Timestamp`, `-Nonce`, `-Event`, `-Delivery-ID`.

## 7. Verify the signature

Dashboard → **Signature Inspector**. Paste the secret, timestamp, nonce,
signature, and the **raw** body exactly as received.

Your secret never leaves the browser — verification is entirely client-side.

If it fails, the inspector tells you which part is wrong. The usual culprit is
re-serializing the body before verifying; see `docs/WEBHOOK_DEBUGGING.md`.

## 8. Watch the delivery

Dashboard → **Deliveries**. Status updates live over SSE (`queued` →
`processing` → `success`/`retrying`/`failed`/`dead_letter`) with no refresh.

If realtime drops, the UI reconciles from the REST API on reconnect — realtime
is a convenience, never the source of truth.

## 9. Force a failure and watch retries

Point the endpoint at a URL that returns `503` (most request-bin services let
you configure the status), then send another test event.

Open the delivery detail page. You'll see attempt 1 recorded with
`http_status: 503` and `error_category: transient_http_error`, plus a
`next_attempt_at`. Celery beat scans for due retries every 10 seconds, so the
next attempt fires on schedule with exponential backoff and jitter.

Try `401` instead to see the contrast: `permanent_http_error`, no retry, goes
terminal immediately. Retrying a deliberate rejection just generates load.

## 10. Exhaust retries into the DLQ

Leave the destination failing. Once `max_retry_attempts` is reached, the job
becomes `dead_letter`. The event, the job, and **every** attempt record are
preserved — nothing is deleted.

Dashboard → **Dead Letter Queue** to inspect it.

## 11. Replay and confirm success

Switch the destination back to returning `200`, then replay from the DLQ
(requires `ADMIN`).

Replay re-queues the same job with its original signed payload — no new logical
event, so idempotency and audit history stay intact. The delivery should now
succeed.

Note: replay resets `attempt_number` to 0, so a replayed job can have two
attempt rows numbered `1`. Order by `started_at` when reading the timeline.

## 12. Integrate with an SDK

Four SDKs live in `sdks/` (Node, Python, Go, Java) and a CLI in `cli/`. See
`docs/sdks/README.md` and `docs/cli/README.md`, plus runnable code in
`examples/`.

---

## Running the checks

```bash
cd backend && pytest -q                 # in-memory SQLite, no services needed
cd backend && ruff check app && mypy app --ignore-missing-imports
cd apps/web && npx tsc --noEmit && npx next lint
```

`CONTRIBUTING.md` has the current authoritative command list.

## Common problems

| Symptom | Cause |
|---|---|
| Event created, never delivered | Celery worker isn't running (step 1) |
| Retries never fire | Celery **beat** isn't running — the worker alone doesn't schedule retries |
| Endpoint rejected on creation | Private/loopback address blocked by SSRF protection (step 3) |
| `/health/ready` returns 503 | Postgres or Redis is down — the body names which |
| Signature won't verify | Body was re-serialized — see `docs/WEBHOOK_DEBUGGING.md` |
| `422` on event publish | Event type must be `namespace.name`, lowercase, one dot |
| `429` on test events | 30/min per organization; use an API key for programmatic traffic |

---

## Related documentation

- `docs/WEBHOOK_DEBUGGING.md` — signatures, error categories, retry/DLQ debugging
- `docs/DEVELOPER_EXPERIENCE.md` — what developer tooling exists and why
- `docs/RELIABILITY.md` — delivery/retry/DLQ semantics in depth
- `README.md`, `CONTRIBUTING.md` — setup and contribution workflow
