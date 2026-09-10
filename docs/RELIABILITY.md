# Delivery Reliability: Invariants, Lifecycle, and Where to Change What

This document exists separately from
[`docs/architecture/README.md`](architecture/README.md) and
[`docs/DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) because it's about one thing
specifically: **RelayHub's core promise that a webhook event is never silently
lost.** Everything here was verified against the actual code, not assumed —
see each section for how.

## The invariant

**A `DeliveryJob` is never silently dropped.** Every job ends in exactly one
of three durable terminal states (`success`, `failed`, `dead_letter`), or sits
in a transient state (`queued`, `processing`, `retrying`) that something is
always actively working to move forward. There is no code path that deletes a
job or forgets about it without recording why.

## Lifecycle

```
EVENT CREATED (events/service.py: publish_event)
       │
       ▼
   QUEUED ──────────────────────────────────────────┐
       │                                             │
       ▼                                             │
  PROCESSING (delivery/executor.py claims the job)    │
       │                                             │
       ▼                                             │
  DELIVERY ATTEMPT (signed HTTP POST to the endpoint) │
       │                                             │
   ┌───┴────┐                                        │
   ▼        ▼                                        │
SUCCESS   FAILURE                                     │
            │                                         │
      ┌─────┴──────┐                                  │
      ▼            ▼                                  │
  retryable    non-retryable                          │
      │            │                                  │
      ▼            ▼                                  │
  RETRYING       FAILED                                │
      │        (terminal, preserved,                   │
      │         see "Non-retryable" below)              │
      ▼                                                │
  next_attempt_at set, backoff delay ─────────────────┘
      │        (check_due_retries re-queues when due)
      ▼
  attempts exhausted (5th failure)?
      │
      ▼
  DEAD_LETTER (preserved, replayable via POST /v1/dlq/{id}/retry)
```

Every arrow above is a real, traced code path — not aspirational:
- `events/service.py`'s `publish_event` creates the `Event` and one
  `DeliveryJob` per subscribed active endpoint, `queued`.
- `delivery/executor.py`'s `execute_delivery_job` does the claim (CAS on
  status, see "Crash safety" below), the signed HTTP call, and the
  success/retry/dead-letter decision, all in one function -- see its own
  `_classify_response` for exactly which failures are retryable.
- `retry/scheduler.py`'s `enqueue_due_retries` (driven by Celery beat's
  `check_due_retries` task, every 10s) is what actually re-queues a
  `retrying` job once its backoff window has passed.
- `retry/reconciliation.py`'s `reconcile_stuck_jobs` is the crash-safety net
  (see below) -- it's not part of the "happy path" above, it's what catches
  jobs the happy path lost track of.

## Retry classification (verified against `delivery/executor.py`'s
`_classify_response`, `_classify_exception`)

| Failure | Category | Retryable? |
|---|---|---|
| 2xx | `SUCCESS` | n/a |
| 408, 429 | `TRANSIENT_HTTP_ERROR` | **Yes** |
| 500-599 (any) | `TRANSIENT_HTTP_ERROR` | **Yes** |
| Any other 4xx (400, 401, 403, 404, 422, ...) | `PERMANENT_HTTP_ERROR` | No |
| Request timeout | `TIMEOUT` | **Yes** |
| Connection refused/reset, DNS failure | `CONNECTION_ERROR` | **Yes** |
| Destination resolves to a private IP (SSRF) | `SSRF_BLOCKED` | No |
| Endpoint has no signing secret configured | `SIGNING_ERROR` | No |

This table is a description of the code, not a separate source of truth --
if you change classification, update `_classify_response`/
`_classify_exception` first and this table second. Tests:
`backend/tests/integration/test_delivery_executor.py` (one test per category
above; 5xx is tested via 503 as a representative of the whole `500-599`
range check, not one test per status code, since they're all the same code
path).

## Backoff and max attempts

Default: `[10, 30, 60, 300]` seconds between attempts 1→2, 2→3, 3→4, 4→5 (so
5 total attempts, the 5th failure triggers dead-lettering) --
`retry/schedule.py`'s `DEFAULT_RETRY_DELAYS_SECONDS`/`DEFAULT_MAX_ATTEMPTS`.
Endpoints can override `max_attempts` individually (`endpoints/models.py`).
`compute_next_retry_delay` is the one place this is computed -- don't
duplicate this logic anywhere else.

## Crash safety

**What happens if a worker dies mid-attempt** (destination may have already
received and processed the request, but the worker crashes before recording
the outcome): the job is stuck in `processing` with no worker left to finish
it. `retry/reconciliation.py`'s `reconcile_stuck_jobs` is the recovery
mechanism, run on a Celery beat schedule:

1. **Lease-based fast path**: if the job's owning worker has a heartbeat
   (`admin/models.py`'s `WorkerHeartbeat`, written by
   `admin/operations.py`'s `upsert_worker_heartbeat`) that's gone stale
   (`WORKER_HEARTBEAT_STALE_AFTER`), the job is confirmed abandoned and
   reset immediately.
2. **Time-heuristic fallback**: if there's no heartbeat info (or it's
   ambiguous), a job stuck in `processing` for longer than a threshold is
   treated as abandoned and reset to `queued` for another attempt.
3. Also recovers jobs stuck in `queued` past a threshold (the "queued but
   the broker dispatch itself failed or was lost" case) and jobs whose
   `retrying` state's `next_attempt_at` was somehow missed by the scanner.

This does not double-count a retry attempt -- resetting to `queued` re-enters
the normal `execute_delivery_job` claim (a CAS on status, see next
paragraph), so a job can't be picked up by two workers at once even if
reconciliation and a live worker race.

**Why a worker crash can never cause a duplicate *scheduling*:** the claim in
`execute_delivery_job` is a compare-and-swap on `status` (`queued`/`retrying`
→ `processing`, in a single `UPDATE ... WHERE status IN (...)` that only one
concurrent caller can win) -- two workers racing for the same job, or a
worker retrying its own claim after reconciliation resets it, cannot both
"win" and process it twice. Tested:
`test_full_retry_loop_scanner_actually_triggers_second_attempt` and the
concurrency-focused tests in `test_reconciliation.py` (see that file's own
test names -- "idempotent and safe to run concurrently" is a real, existing
test, not a description I'm adding here).

**Why a worker crash can (rarely) cause a duplicate *HTTP request* to the
destination**, and why that's a documented, accepted tradeoff rather than a
bug: if the destination actually received and processed the request, but the
worker died before the response was recorded, reconciliation will
legitimately retry -- from RelayHub's side, "no confirmed success" and
"confirmed failure" look the same. This is why RelayHub signs every request
with the same deterministic signature for retries of the same attempt
sequence (see `delivery/signing.py`) and why documentation to webhook
consumers (`docs/webhooks/README.md`) tells them to treat delivery as
at-least-once, not exactly-once, and dedupe on the event ID if their own
processing isn't naturally idempotent. RelayHub cannot make the *destination
system* idempotent; it can and does make its own retry bookkeeping
consistent.

## Idempotency (publisher side)

A client publishing to `POST /v1/events` can pass an `idempotency_key`.
`events/service.py`'s `publish_event`:

1. Checks for an existing `Event` with the same
   `(organization_id, idempotency_key)` first -- if found, returns it
   unchanged (no new `DeliveryJob`s created).
2. Otherwise inserts a new `Event`, protected by a real database `UNIQUE`
   constraint on `(organization_id, idempotency_key)` -- if two requests
   race, the loser's `flush()` raises `IntegrityError`, which is caught,
   rolled back, and re-queried to return the winner's row. **Verified via
   code review**: the rollback-and-return-existing logic is correct. The
   specific concurrent-race branch (two true simultaneous requests) does not
   have a dedicated automated test -- deterministically forcing that exact
   timing window turned out to be impractical against the SQLite backend
   this suite uses by default (its `StaticPool` shares one physical
   connection, so genuinely independent concurrent transactions aren't
   reliably reproducible in-process) without fragile, environment-specific
   test machinery. Flagged here as a known, accepted testing gap -- the
   sequential case (the far more common real-world scenario: a client
   retrying after its own timeout) is tested
   (`test_idempotency_key_prevents_duplicate_event_and_duplicate_jobs`), and
   the database-level `UNIQUE` constraint enforces correctness regardless of
   test coverage.

## DLQ and replay

A job that exhausts its attempt budget becomes `dead_letter` -- the `Event`,
the `DeliveryJob`, and every `DeliveryAttempt` (full HTTP status/timing/error
history) are preserved, never deleted. `dlq/service.py`'s
`retry_dead_letter_job` (`POST /v1/dlq/{id}/retry`) re-queues the **same**
job with its **original** signed payload -- it does not create a new
logical event, so idempotency/audit history stays intact. Tenant-scoped:
every DLQ query filters by `organization_id` via `tenant_select`. Bulk retry
(`POST /v1/dlq/bulk-retry`) is the same single-job path called in a loop, not
a separate implementation.

## Tenant isolation on this path specifically

Every query touching `Event`, `DeliveryJob`, `DeliveryAttempt` in
`events/`, `delivery/`, `retry/`, `dlq/`, and `logs/` goes through
`db/tenant_query.py`'s `tenant_select(Model, organization_id)` -- confirmed
via code review of each module's service layer during this audit. The one
documented, intentional exception is `admin/operations.py`'s
`admin_search_delivery_jobs`, which is deliberately global (platform-admin
only, gated by `require_platform_admin`, not a per-org role) -- see that
function's own docstring.

## Celery / Redis responsibilities on this path

- **`worker`** (default queue): `deliver_webhook` task → `execute_delivery_job`.
- **`beat`**: `check_due_retries` (every 10s) → `enqueue_due_retries`;
  `reconcile_stuck_jobs` on its own schedule; `cleanup_expired_delivery_logs`.
  **A missing `beat` process means retries past the first attempt simply
  never fire** -- this happened for real in production once; see
  `docs/architecture/README.md`'s "Celery / workers" section for the
  incident and the fix (`backend/start.sh`).
- **Redis**: the Celery broker/result backend (`CELERY_BROKER_URL`/
  `CELERY_RESULT_BACKEND`) and separately the rate-limiter's sliding-window
  counters (`REDIS_URL`) -- see `docs/CONFIGURATION.md`.

## Where to change what

Matches [`docs/WHERE_TO_MAKE_CHANGES.md`](WHERE_TO_MAKE_CHANGES.md)'s more
detailed versions of these -- summarized here for this specific lifecycle:

| Change | File |
|---|---|
| What counts as a retryable failure | `delivery/executor.py`'s `_classify_response`/`_classify_exception` |
| Backoff delay / max attempts | `retry/schedule.py`'s `compute_next_retry_delay` |
| When a `retrying` job actually gets re-attempted | `retry/scheduler.py`'s `enqueue_due_retries` |
| Crash/stuck-job recovery | `retry/reconciliation.py` |
| DLQ listing/retry/discard/export | `dlq/service.py` |
| The actual signed HTTP call | `delivery/executor.py`, `delivery/signing.py` |
| SSRF/private-IP protection | `endpoints/security.py` (save-time), `delivery/connect_time_security.py` (connect-time) |

## How to run the tests that protect this

```bash
cd backend
pytest tests/integration/test_delivery_executor.py tests/integration/test_delivery_attempt_ux.py -v   # delivery + classification
pytest tests/integration/test_retry_engine.py -v                                                       # retry scheduling
pytest tests/integration/test_reconciliation.py -v                                                      # crash safety
pytest tests/integration/test_dlq.py -v                                                                 # DLQ + replay
pytest tests/integration/test_events.py -v                                                              # idempotency
```

Or the full suite, which is what CI actually runs: `pytest -q` (SQLite) --
CI additionally re-runs everything against real PostgreSQL+Redis (the
`backend-postgres` job) specifically because SQLite's laxer constraint/type
checking can hide real bugs (its `UNIQUE` constraint enforcement, which the
idempotency mechanism above depends on, behaves the same as Postgres's, but
this is exactly the kind of thing worth a real second engine's confirmation).
