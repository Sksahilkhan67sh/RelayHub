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

**`attempt_number` is scoped to the current delivery cycle, not the job's
full lifetime.** `retry_dead_letter_job` deliberately resets
`job.attempt_number = 0` on replay, to give the job a full fresh retry
budget rather than counting against the exhausted one. This means a job
that has ever been replayed can have two (or more) `DeliveryAttempt` rows
sharing the same `attempt_number` -- one from before the replay, one from
after. Nothing is overwritten or lost (every attempt row persists,
independently queryable by its own `id`/`started_at`), but `attempt_number`
alone is not a safe way to identify or dedupe "the Nth attempt" for a job
that has been through a replay. Found and fixed during Phase 1 hardening:
`DeliveryJob.attempts`'s relationship ordering was `by="attempt_number"`,
which has no defined tie-break order in SQL once that column isn't unique
per job -- changed to `by="started_at"` (always monotonic, unaffected by
the reset) so `job.attempts` is reliably chronological regardless. A
stronger fix (an explicit `execution_number`/`replay_count` column stamped
onto each attempt, giving a truly unique `(execution_number,
attempt_number)` key) was deliberately **not** implemented in this phase --
it's a real schema change for a problem that doesn't lose data today, just
ambiguity in one derived field; revisit if a consumer ever needs to
distinguish pre- and post-replay attempts programmatically rather than by
`started_at` order. See `tests/integration/test_reliability_phase1_e2e.py`.

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

## Phase 1 reliability hardening (2026-09-13)

Findings from a dedicated hardening pass, each backed by direct evidence
(code inspection, real-Postgres migration/test runs, and live Render log
inspection where noted) rather than assumption:

- **"delivery_job=... already claimed by another worker, skipping" is
  correct, expected behavior, not a bug.** Confirmed via live production
  logs (2026-09-11, a burst of the same job IDs claimed 2-3 times each in
  quick succession, each duplicate correctly rejected by the CAS claim in
  `executor.py`'s `_claim_job`) and via `test_duplicate_claim_is_prevented`.
  This is the intended outcome of at-least-once scheduling racing against
  itself (a worker restart re-triggering a re-enqueue, or two workers
  legitimately racing on the same due job) -- exactly one of the racing
  claims wins, the rest are safely no-ops, no delivery is duplicated or
  lost. Do not remove or weaken this.
- **429/5xx/timeout/connection-error retry-then-recover is verified
  end-to-end**, not just at the single-attempt classification level --
  see `test_reliability_phase1_e2e.py`'s `test_429_429_200_full_recovery_e2e`,
  `test_503_503_200_full_recovery_e2e`, `test_timeout_then_successful_retry_e2e`,
  `test_connection_error_then_successful_retry_e2e`, each asserting the
  actual `delivery_attempts` rows (status codes, attempt numbers), not
  just the job's final state.
- **Queue-submission-after-DB-commit failure is already handled correctly**
  (`events/service.py`'s `publish_event` and `dlq/service.py`'s
  `retry_dead_letter_job` both commit the durable state change first, then
  try to enqueue, catching and logging any broker failure rather than
  raising -- reconciliation's stale-`queued` pass recovers it within
  `STALE_DISPATCH_AFTER`). This is effectively a transactional-outbox
  pattern already, just without a separate outbox table. No outbox was
  added in this phase -- there's no demonstrated gap it would close.
- **Composite index added:** `(status, next_attempt_at)` on `delivery_jobs`
  (migration `0020`), justified by `retry/scheduler.py`'s
  `enqueue_due_retries` query, which runs every 10 seconds forever.
  Tested against real PostgreSQL 16: fresh-DB `upgrade head`,
  upgrade-from-0019, and `downgrade` all confirmed.
- **`(organization_id, status, completed_at)` composite index: NOT added.**
  No query in the codebase filters on that exact triple. The nearest real
  query, `logs/retention.py`'s daily `cleanup_expired_delivery_logs`, filters
  `organization_id` + `completed_at` only (no `status` predicate --
  `completed_at IS NOT NULL` already implies a terminal job), and isn't a
  demonstrated bottleneck at current data volume. Revisit if retention or
  log-search read volume grows.
- **Health check endpoints already exist and are correctly designed**:
  `GET /health/live` (cheap, no dependency checks -- process-alive only) and
  `GET /health/ready` (checks DB + Redis, returns 503 if either is down) in
  `app/main.py`. **REQUIRES MANUAL ACTION**: Render's service-level
  `healthCheckPath` setting is currently empty, so Render itself isn't
  using either endpoint for its own health signal (the Dockerfile's own
  `HEALTHCHECK` directive does use `/health/live`, so container-level
  health checking works; Render's platform-level check does not). No tool
  available in this environment can change that setting -- set it to
  `/health/live` (or `/health/ready` if you want Render to restart on a
  dependency outage, not just a hung process) in the Render dashboard
  under this service's Settings.
- **Backup / PITR: NOT VERIFIED / REQUIRES MANUAL ACTION.** The current
  production database (`relayhub-db-user`) is on Render's free Postgres
  plan, which does not include automated backups or point-in-time
  recovery -- confirmed via the Render API (`plan: "free"`). `scripts/
  backup_db.sh` / `restore_db.sh` exist and are a correct manual
  `pg_dump`/`pg_restore` pair, but nothing runs them on a schedule (no
  cron, no CI job, no Render cron service). The free-plan database also
  has a Render-side `expiresAt` -- the same mechanism that suspended the
  previous database. **RPO/RTO: NOT YET ESTABLISHED** -- there is currently
  no backup cadence to derive a real RPO from, and no rehearsed restore to
  derive a real RTO from. Until a backup schedule exists (either an
  upgraded Render plan with managed backups, or a scheduled job running
  `backup_db.sh` against external storage), this is the single largest
  reliability gap in the system and is outside what this phase could
  safely implement without new infrastructure credentials.
- **Redis has no persistence** (`persistenceMode: off`, free tier) --
  unchanged finding from the prior audit, not addressed in this phase
  (would require a paid Redis plan).

## How to run the tests that protect this

```bash
cd backend
pytest tests/integration/test_delivery_executor.py tests/integration/test_delivery_attempt_ux.py -v   # delivery + classification
pytest tests/integration/test_retry_engine.py -v                                                       # retry scheduling
pytest tests/integration/test_reconciliation.py -v                                                      # crash safety
pytest tests/integration/test_dlq.py -v                                                                 # DLQ + replay
pytest tests/integration/test_events.py -v                                                              # idempotency
pytest tests/integration/test_reliability_phase1_e2e.py -v                                              # mixed-code retry E2E, cross-tenant, replay ordering
```

Or the full suite, which is what CI actually runs: `pytest -q` (SQLite) --
CI additionally re-runs everything against real PostgreSQL+Redis (the
`backend-postgres` job) specifically because SQLite's laxer constraint/type
checking can hide real bugs (its `UNIQUE` constraint enforcement, which the
idempotency mechanism above depends on, behaves the same as Postgres's, but
this is exactly the kind of thing worth a real second engine's confirmation).
