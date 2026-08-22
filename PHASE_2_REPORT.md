# RelayHub — Phase 2: Reliability Hardening Report

**Scope note up front:** this pass audited the full delivery-reliability path (event
ingestion → DB → queue → worker → delivery → retry → DLQ → replay) and implemented
fixes for the real, verified gaps found. It did **not** attempt every one of the 28
sections in the phase brief to the same depth — the codebase entering this phase was
already unusually solid (CAS-based claiming, DB-as-source-of-truth ordering,
idempotency keys, SSRF re-validation at connect time, tenant isolation via a
structural query mixin, jittered backoff). This report is honest about what was
actually verified versus what was inspected and found already correct versus what
is explicitly deferred. See "Remaining Risks" at the end.

## Reliability Audit

Inspected, by reading the actual source (not prior reports):
`events/service.py` (ingestion + DB transaction boundary), `delivery/models.py`
(DeliveryJob/DeliveryAttempt schema), `delivery/executor.py` (claim + execute +
finish state machine), `retry/schedule.py` (backoff computation), `retry/scheduler.py`
(due-retry scanning), `dlq/service.py` (DLQ retry/bulk-retry/delete/export),
`common/queue_client.py` (Celery dispatch abstraction), `workers/tasks.py` /
`workers/celery_app.py` (Celery config, beat schedule, task bridge), `core/health.py`
+ `main.py` (liveness/readiness), `admin/service.py` (queue depth / system health /
manual force-retry), plus the existing test suite (`tests/integration/test_retry_engine.py`,
`test_delivery_executor.py`, `tests/unit/test_retry_schedule.py`) to understand what
was already covered.

| Component | Failure mode | Prior behavior | Event-loss risk | Fixed this phase |
|---|---|---|---|---|
| Worker | crash/kill *after* CAS claim commits, *before* delivery finishes | Celery redelivers (task_acks_late + task_reject_on_worker_lost), but redelivery hits `_claim_job`, finds status=processing, raises `JobAlreadyClaimedError` → treated as "someone else has it" | **Critical — silent, permanent.** Job stuck in `processing` forever, no error surfaced. | ✅ `reconcile_stuck_jobs` |
| Queue dispatch | `queue_client.enqueue()` fails at publish time (Redis/broker unreachable) | Exception propagated out of `publish_event`, turning an already-committed DB write into a 500 to the caller | Medium — row not lost, but response was falsely a failure, and nothing re-dispatched it until an operator noticed | ✅ caught + logged; reconciliation backstop |
| Queue dispatch | same, in `enqueue_due_retries` (10s scanner) | One failing enqueue in a batch raised, aborting the rest of that tick's due jobs | Medium — delayed, not lost (next tick would rescan), but reduces throughput under partial broker degradation | ✅ per-job try/except |
| Queue dispatch | same, in DLQ retry / bulk retry / admin force-retry | Same shape as the two rows above | Low-medium — same as above | ✅ caught + logged, same pattern as #2/#3 (added in a follow-up pass) |
| DB | transaction failure during event/job creation | `db.flush()` under a single transaction; `IntegrityError` on idempotency race already handled with re-select of the winner | None found — correct as-is | No change needed |
| Retry engine | attempt numbering / exhaustion / jitter | Already correct and tested (`test_retry_schedule.py`, `test_retry_engine.py`) | None found | No change needed |
| DLQ transition | retry exhausted → DLQ | Single-transaction, preserves full `DeliveryAttempt` history, clears `next_attempt_at` | None found | No change needed |
| Stuck job detection | no lease/heartbeat table exists (confirmed absent, honestly documented in `admin/service.py`) | Nothing detected abandoned jobs automatically; only a manual admin force-retry existed | Critical, see above | ✅ time-based heuristic in reconciliation (documented as heuristic, not a true lease) |
| Worker health | no heartbeat table | `get_system_health` explicitly reports DB + queue-depth only | Not a loss risk by itself, but no automated detection of a dead worker fleet | Not built this pass — real fix needs a new table + migration (see Remaining Risks) |

## Problems Found & Fixed

### 1. Critical — jobs abandoned mid-processing were unrecoverable forever

**Root cause:** `_claim_job` commits the `processing` status transition *before* any
actual delivery work happens. Celery's `task_acks_late=True` +
`task_reject_on_worker_lost=True` correctly redelivers the message if the worker
process dies mid-task — but the redelivered task's own claim attempt now sees
`status=processing` (not `queued`/`retrying`), so `_claim_job` raises
`JobAlreadyClaimedError`, and `tasks.py` treats that as "another worker already has
this, skip it." No other worker does. The job silently disappears from the pipeline
— exactly the failure mode Phase 2 exists to eliminate.

**Fix:** `app/modules/retry/reconciliation.py` — a new `reconcile_stuck_jobs()`
function, run every 60s via a new Celery beat task (`reconcile_stuck_jobs` /
`reconcile_stuck_jobs_task`). It bulk-transitions any `processing` job whose
`updated_at` (bumped by the CAS claim's own commit) is older than
`STUCK_PROCESSING_AFTER` (10 minutes — several times larger than the largest
allowed endpoint timeout) back to `retrying` with an immediate `next_attempt_at`,
then re-enqueues it. The job re-enters the exact same claim/execute path as any
normal retry — no special "recovered" state to maintain.

This is explicitly a **heuristic**, not a true lease, because no worker-heartbeat
table exists in this codebase. A pathological case — a request that hangs for
longer than `STUCK_PROCESSING_AFTER` without timing out — could theoretically cause
a second concurrent attempt. In practice the executor's own HTTP timeout
(`endpoint.timeout_seconds`, bounded well under 10 minutes by `endpoints/schemas.py`
validation) makes that essentially unreachable. Documented as a known limitation
below rather than glossed over.

### 2. Medium — broker outage during publish turned a successful write into a false failure

**Root cause:** `events/service.py`'s `publish_event` calls
`queue_client.enqueue(job.id)` *after* the DB commit (correct ordering — the row is
never lost), but with no error handling. If the broker call itself raised (Redis
down, network partition), the exception propagated straight out of the request
handler, returning a 500 to a caller whose event *had* actually been durably
accepted. A customer reading that 500 could reasonably (and incorrectly) conclude
the event was never received and re-publish it — masking the real gap rather than
fixing it.

**Fix:** wrapped the per-job `enqueue()` call in try/except; a broker failure is
logged and the request still returns success, since the row is genuinely durable
and `reconcile_stuck_jobs`'s "stale queued" pass (see below) will re-dispatch it
within `STALE_DISPATCH_AFTER` (2 minutes).

### 3. Medium — one failing enqueue in the due-retry scanner aborted the rest of that tick

**Root cause:** `enqueue_due_retries` looped over due jobs calling `enqueue()` with
no error isolation; one broker failure mid-loop meant every subsequent due job in
that batch was skipped for the tick (they'd be picked up on the *next* 10s tick, so
this was a throughput/latency issue under partial degradation, not outright loss —
still worth fixing since Phase 2's bar is "no silent surprises," and a stack trace
eating the rest of a batch is a silent one).

**Fix:** per-job try/except inside the loop; one failure is logged and the loop
continues.

### 4. Medium — same broker-outage gap in DLQ retry, bulk DLQ retry, and admin force-retry

**Root cause:** identical shape to problem #2, in three more call sites:
`dlq/service.py`'s `retry_dead_letter_job` (single DLQ retry) and
`bulk_retry_dead_letter_jobs`, and `admin/service.py`'s `force_retry_delivery_job`.
Each resets a job's status to `queued` and commits, then calls
`queue_client.enqueue()` unguarded — a broker failure there would surface as a
failed retry request even though the retry had, in DB terms, already succeeded.

**Fix:** same try/except pattern as problem #2, applied to all three call sites; the
bulk-retry loop also isolates one job's dispatch failure from the rest of the batch,
same as the due-retry scanner fix (problem #3). All three are covered by
reconciliation's stale-`queued` backstop.

### 5. Backstop — reconciliation also re-dispatches stale `queued`/`retrying` rows

(Numbering follows on from problem #4 above.) Beyond the mid-processing-crash case, `reconcile_stuck_jobs` also re-enqueues:
- `queued` jobs whose `updated_at` is older than `STALE_DISPATCH_AFTER` (2 min) —
  covers the case where the initial `enqueue()` failed (problem #2 above) even
  before that fix landed, and covers it going forward as defense-in-depth even with
  the fix in place.
- `retrying` jobs whose `next_attempt_at` has passed by more than
  `STALE_DISPATCH_AFTER` — backstop for the 10s scanner itself missing a tick or its
  own enqueue failing (problem #3).

Re-enqueuing a job that wasn't actually lost (just sitting in a normal queue
backlog) is a harmless duplicate broker message: the executor's existing CAS claim
(`_claim_job`) makes a second concurrent delivery of an already-claimed job
impossible — the same safety property `retry/scheduler.py`'s docstring already
relies on for its own duplicate-tick case.

### 6. Follow-up — real worker-fleet health, replacing the honest "not tracked" gap

**Background:** the original audit found that `admin/service.py`'s
`get_system_health` deliberately reported "worker registry / live process health is
explicitly NOT included here" rather than fabricating a `workers: healthy` field
with no data behind it — an honest gap, not a bug, but still a real observability
hole (Phase 2 section 9, "Worker Health").

**Fix:** added a new `worker_heartbeats` table (migration `0014`) and a background
heartbeat loop that starts in each real Celery worker process via the
`worker_process_init` signal (`app/workers/celery_app.py`) — deliberately *not*
triggered by simply importing the module, so the FastAPI process (which imports
`celery_app` lazily through `RedisQueueClient.enqueue`) never spins one up. Each
worker process writes/updates its own row (keyed by `hostname-pid`) every 15
seconds; `admin/service.py`'s new `get_worker_health()` reports a worker unhealthy
once its heartbeat is older than 90 seconds (6x the write interval, so one missed
tick under load doesn't false-flag a healthy worker). `get_system_health` now
returns real `worker_health` data instead of omitting the field.

This closes the "no worker heartbeat table" gap from the original report's
Remaining Risks — but at the time it was fleet-level liveness only ("is this worker
process alive at all"), not a per-job lease. **Closed in a further follow-up (see
Problem #7 below):** `reconcile_stuck_jobs` now ties a specific in-flight job to the
specific worker holding it.

Also closed: the "DLQ concurrent-double-retry" test noted as missing in the
original report. `test_double_retry_of_same_dlq_job_is_safe` verifies that a second
retry of an already-retried job is safely rejected (404, since
`_get_dlq_job_or_404` only matches `status == dead_letter`) rather than resetting
the job's attempt history a second time — confirming `dlq/service.py`'s existing
filter-based approach is safe without needing any new locking.

### 7. Follow-up — a real per-job lease, not just fleet-level liveness

**Background:** Problem #6 gave `reconcile_stuck_jobs` a way to know whether *any*
workers were alive, but not whether the *specific* worker holding a given stuck job
was alive — the stuck-processing check still relied purely on
`DeliveryJob.updated_at` and a fixed 10-minute wait, exactly as before Problem #6.

**Fix:** two new nullable columns on `DeliveryJob` — `claimed_by_worker_id`,
`claimed_at` (migration `0015`) — populated by `_claim_job`
(`delivery/executor.py`) at the same CAS-claim commit that already flips status to
`processing`. `reconcile_stuck_jobs`' new `_find_stuck_processing_job_ids` helper
now checks, for each job stuck in `processing`, whether its claiming worker has a
heartbeat row:
- **Worker confirmed alive** (fresh heartbeat) → never recovered on elapsed time
  alone, however long it's been — a live worker means real work may still be
  happening, and recovering the job anyway would risk a duplicate concurrent
  delivery attempt, which is exactly what a lease exists to prevent.
- **Worker confirmed dead** (heartbeat stale past `LEASE_WORKER_STALE_AFTER`, 90s)
  → recovered *immediately*, without waiting out the old 10-minute window. This is
  the actual value of a real lease over a time heuristic: much faster recovery when
  the failure is real, not just "eventually recovers either way."
- **No usable lease** (job claimed before this migration, or a `claimed_by_worker_id`
  with zero rows in `worker_heartbeats`) → falls back to the original
  `STUCK_PROCESSING_AFTER` time heuristic, unchanged from before.

A small `LEASE_GRACE_PERIOD` (30s) covers the narrow window right after a claim,
before that worker's first heartbeat write has necessarily landed, so a job isn't
misjudged as lease-covered-but-dead in the first moment after being claimed.

One correctness detail worth calling out: the `worker_id` written by the heartbeat
loop (`celery_app.py`) and the `worker_id` passed to `_claim_job` (via
`tasks.py`) previously used two independently-written derivations
(`socket.gethostname()` vs. `os.uname().nodename`) that agree on typical Linux
hosts but weren't guaranteed to. A mismatch here would have silently broken the
lease (a claimed job's `claimed_by_worker_id` would never match any
`worker_heartbeats` row, silently degrading every job to the time-heuristic
fallback with no error surfaced). Extracted both into one shared
`app/workers/identity.get_worker_id()` so they're structurally guaranteed to agree.

Regression tests: `test_claim_records_worker_lease` (the lease fields are actually
populated on claim), `test_reconciliation_lease_overrides_time_heuristic_when_worker_alive`
(a job stuck for 30 minutes — 3x past the time heuristic — is correctly left alone
because its worker is still heartbeating), `test_reconciliation_lease_recovers_job_fast_when_worker_confirmed_dead`
(a job stuck for only 2 minutes — nowhere near the 10-minute heuristic — is
recovered immediately because its worker's heartbeat is confirmed stale), and
`test_reconciliation_falls_back_to_time_heuristic_when_worker_has_no_heartbeat_history`
(a job whose worker has zero heartbeat rows correctly falls back to the original
behavior rather than being treated as either confirmed-alive or confirmed-dead).

### 8. Follow-up — real delivery-latency/retry-rate/DLQ-rate/stuck-jobs metrics

**Background:** Phase 2 section 16 ("Observability") asks for delivery latency,
retry rate, DLQ rate, and stuck-job visibility beyond what `get_queue_depth`
already covered (queue depth by status, success/failure counts in the last hour).
There was no metrics-export pipeline (Prometheus/OTel) to plug these into — see
Remaining Risks, unchanged — so this stays within the existing
admin-endpoint-based monitoring pattern rather than introducing a new dependency,
per the "use the existing monitoring architecture, avoid unnecessary dependencies"
instruction.

**Fix:** new `get_delivery_metrics()` (`admin/service.py`) and `GET
/admin/delivery-metrics` endpoint, computing over a configurable time window
(default 1 hour): average and p95 delivery latency (from `DeliveryAttempt.duration_ms`
for successful attempts), retry rate and DLQ rate (from completed `DeliveryJob`
rows' `attempt_number`/`status`), and a live count of jobs currently stuck in
`processing` past the same threshold `reconcile_stuck_jobs` uses for its own
time-heuristic fallback — so this number means "how many jobs would reconciliation
act on right now if the lease didn't apply," not an arbitrary separate threshold.
All rate/latency fields are `None` (not a divide-by-zero error or a misleading `0`)
when there's no data yet in the window, correctly distinguishing "no deliveries
happened" from "0% failure rate."

Regression tests: `test_delivery_metrics_empty_state` (nulls, not errors, with zero
data), `test_delivery_metrics_reflects_real_deliveries` (a real successful delivery
moves `sample_size`, `avg_delivery_latency_ms`, and `dlq_rate`/`retry_rate`
together, proving the numbers come from actual rows), and
`test_delivery_metrics_stuck_jobs_count` (a job artificially aged past the
threshold is counted, proving the stuck-jobs read is live, not cached/fake).

## Database

Two migrations this phase, both additive-only (no changes to existing columns, no
backfill needed):
- `0014_worker_heartbeats.py` — new `worker_heartbeats` table.
- `0015_delivery_job_claim_lease.py` — two new nullable columns on `delivery_jobs`
  (`claimed_by_worker_id`, `claimed_at`) plus an index on the former.

**Now verified against a real PostgreSQL 16 instance**, not just structurally. A
Postgres 16 server was installed and started in this sandbox specifically to close
this gap:

- `alembic upgrade head` run against a **fresh, empty database**: all 15 migrations
  (`0001`–`0015`) applied cleanly in order, including both new ones, with no errors.
- Schema inspected directly via `psql \d`: `worker_heartbeats` has exactly the
  columns/types/indexes the model declares (including the `UNIQUE` index on
  `worker_id`); `delivery_jobs` has the two new nullable lease columns and the new
  index on `claimed_by_worker_id`.
- **Downgrade/upgrade round-trip**: `alembic downgrade 0013` cleanly dropped both
  the lease columns and the entire `worker_heartbeats` table (confirmed via `\d`
  showing them gone), then `alembic upgrade head` cleanly re-applied both — a full
  round-trip with no errors in either direction.
- **ORM logic exercised directly against real Postgres** (not SQLite) for the
  pieces most likely to behave differently between the two: `upsert_worker_heartbeat`
  / `get_worker_health` (confirmed healthy/stale classification and upsert
  idempotency, and confirmed Postgres returns proper tz-aware `datetime`s so the
  SQLite-only naive-datetime workaround in that code is inert here, as intended);
  `_claim_job`'s CAS logic (confirmed a second concurrent claim attempt is rejected
  with `JobAlreadyClaimedError` and does not overwrite the original claim's lease
  fields); and the full `reconcile_stuck_jobs` lease-vs-time-heuristic decision
  logic end-to-end against real `DeliveryJob`/`WorkerHeartbeat` rows with real
  foreign-key constraints (organization → endpoint → event → delivery_job) — all
  three scenarios (worker alive → left alone, worker confirmed dead → recovered
  fast via lease, no lease signal → time-heuristic fallback) produced identical
  results to the SQLite-based automated test suite.

Not done: the pytest suite itself still runs against SQLite (`tests/conftest.py`
hardcodes `sqlite+aiosqlite:///:memory:` for speed and zero external dependencies)
— that's an existing, deliberate project choice from before this phase, not
something this pass changed. The verification above was done as targeted,
standalone scripts exercising the same code paths directly against Postgres,
specifically to catch anything the SQLite-based suite could mask (tz-naive
datetimes being the known example — confirmed a non-issue). If you want an
ongoing Postgres-backed test tier in CI rather than one-off verification, that's a
larger, separate decision about the test suite's architecture, not something folded
into this fix.

`reconcile_stuck_jobs`' stuck-processing detection (problem #1) now checks the new
lease columns first and only falls back to the `DeliveryJob.updated_at` time
heuristic (already auto-bumped by `TimestampMixin`'s `onupdate=func.now()`) when no
usable lease signal exists — see Problem #7 above for the full detection logic.

## Queue

- `publish_event`, `enqueue_due_retries` now tolerate individual broker-dispatch
  failures without losing the durable DB state or (in `publish_event`'s case)
  falsely failing an already-successful request.
- New `reconcile_stuck_jobs` closes the gap where a lost/failed broker message was
  otherwise unrecoverable.

## Workers

Fixed the specific `task_acks_late` + CAS-claim interaction that left crashed
workers' jobs permanently stuck (see Problem #1). **Also added:** a real
worker heartbeat/health table — see Problem #6 above and the Workers / Admin
section below. **Now unified** (Problem #7): `reconcile_stuck_jobs`' stuck-*job*
detection checks the specific claiming worker's heartbeat first, falling back to
the `updated_at` time heuristic only when no lease signal is available.

## Retry

No changes to the retry math itself (`retry/schedule.py`) — audited and already
correct (attempt numbering, per-endpoint override, max-attempts exhaustion → `None`,
jitter). Hardened only the *dispatch* side (problems #2 and #3).

## DLQ

Audited `dlq/service.py`: DLQ transition itself is already a single-transaction
commit inside `executor.py`'s `_finish`, attempt history is never destroyed,
`next_attempt_at` is cleared on both the `failed` and `dead_letter` terminal paths —
no gap found there, no change made.

Did find and fix the broker-outage gap from problem #4 above in both
`retry_dead_letter_job` (single retry) and `bulk_retry_dead_letter_jobs`, matching
the pattern already applied to `publish_event`. Regression tests:
`test_retry_dlq_job_survives_queue_dispatch_failure` and
`test_bulk_retry_survives_partial_queue_dispatch_failure` (the latter also confirms
one job's dispatch failure doesn't stop the other job in the same batch from being
dispatched).

Concurrent-double-retry-from-DLQ: **now covered by a real test**,
`test_double_retry_of_same_dlq_job_is_safe` — verifies a second retry of an
already-retried job is rejected (404 via `_get_dlq_job_or_404`'s `status ==
dead_letter` filter) rather than double-resetting attempt history, and that exactly
one broker dispatch happened, not two.

## Replay

Not modified. Reused DLQ retry path already preserves original attempt history,
resets the job to a controlled new lifecycle (`attempt_number=0`, `status=queued`),
and remains tenant-scoped via `_get_dlq_job_or_404`'s `organization_id` filter — read
and confirmed correct, no fix needed.

## Workers / Admin

`admin/service.py`'s `force_retry_delivery_job` (the one path that can unstick a job
in *any* status, including `processing`, unlike the customer-facing DLQ retry) had
the same unguarded-enqueue gap as problem #4 — fixed the same way, with
`test_force_retry_survives_queue_dispatch_failure` covering it.

`get_system_health` now also returns real `worker_health` data (see Problem #6) —
`healthy_count`, `unhealthy_count`, and a per-worker breakdown with
`last_heartbeat_at` and a computed `healthy` flag — sourced from the new
`worker_heartbeats` table rather than being absent from the response. Covered by
`test_system_health_reports_worker_heartbeats` (fresh heartbeat → healthy, stale
heartbeat → unhealthy) and
`test_worker_heartbeat_upsert_updates_existing_row_not_duplicates` (re-heartbeating
under the same `worker_id` updates in place, doesn't accumulate rows).

## Security

Not re-run as a full regression pass this phase (the audit report from the prior
phase already covers tenant isolation broadly). Spot-checked that
`reconcile_stuck_jobs` and its new Celery task operate cluster-wide by design (it's
an internal maintenance task with no tenant-scoped API surface, no user input, and
no new route) — there is no new attack surface introduced by this phase's changes.
The new `worker_heartbeats` table and its write path are similarly internal-only:
no tenant scoping applies (it's platform infrastructure, not tenant data) and it's
only ever read through the existing `require_platform_admin`-gated `system-health`
endpoint — same authorization boundary as the rest of `admin/service.py`, not a new
one. The new `delivery-metrics` endpoint sits behind the same
`require_platform_admin` dependency as every other route in this router.

## Observability

Added structured `logger.warning` calls in `reconcile_stuck_jobs` (when anything is
recovered) and in the queue-dispatch-failure paths (problems #2/#3/#4), so operators
can see reconciliation activity and dispatch failures in logs. Also added: real
worker-fleet liveness surfaced through `system-health` (Problem #6), and real
delivery-latency/retry-rate/DLQ-rate/stuck-jobs metrics surfaced through the new
`delivery-metrics` endpoint (Problem #8) — both are genuine new observability
signals, not just log lines, and together close most of what Phase 2 section 16
("Observability") and section 9 ("Worker Health") ask for.

Still **not** added: Prometheus/OTel metrics export — `OTEL_EXPORTER_OTLP_ENDPOINT`
exists as an unused config setting from before this phase; no metrics-export
instrumentation exists anywhere in this codebase yet, and wiring one up from scratch
remains judged out of scope for a reliability-focused pass with an already very
large surface. This is a real, documented gap, not a silent omission.

## Chaos Testing

Tested directly, with real (not simulated-in-prose) code:

| Scenario | Result |
|---|---|
| Worker abandons job after CAS claim commits (simulated crash) | **PASS** — `test_job_abandoned_in_processing_is_unrecoverable_without_reconciliation` first proves the bug exists in isolation, then `test_reconciliation_recovers_job_stuck_in_processing` proves the fix recovers it and it completes a real subsequent delivery |
| Recently-claimed job (a few seconds old) is *not* mistaken for stuck | **PASS** — `test_reconciliation_does_not_touch_recently_processing_job` |
| Broker/Redis dispatch failure at publish time | **PASS** — `test_publish_survives_queue_dispatch_failure`: request still succeeds, row stays durably `queued` |
| Broker dispatch failure mid-batch in the due-retry scanner | **PASS** — `test_enqueue_due_retries_survives_one_broker_failure`: the other job in the same tick still gets dispatched |
| Row stuck in `queued` with a lost dispatch message | **PASS** — `test_reconciliation_requeues_stale_queued_job` |
| `retrying` job whose scheduled retry was missed by the normal scanner | **PASS** — `test_reconciliation_requeues_missed_retry` |
| Reconciliation run twice back-to-back (idempotency / no double-recovery) | **PASS** — `test_reconciliation_is_idempotent_and_safe_to_run_concurrently` |
| Destination HTTP 500/503/429/401, timeout, connection failure | **PASS** — already covered by pre-existing `test_delivery_executor.py` / `test_retry_engine.py`, re-run and confirmed still passing |
| Retry exhaustion → DLQ | **PASS** — pre-existing `test_job_moves_to_dead_letter_after_exhausting_endpoint_override_attempts`, re-confirmed |
| Broker dispatch failure during DLQ single retry | **PASS** — `test_retry_dlq_job_survives_queue_dispatch_failure` |
| Broker dispatch failure mid-batch during DLQ bulk retry | **PASS** — `test_bulk_retry_survives_partial_queue_dispatch_failure` |
| Broker dispatch failure during admin force-retry | **PASS** — `test_force_retry_survives_queue_dispatch_failure` |
| Duplicate/concurrent DLQ retry of the same job | **PASS** — `test_double_retry_of_same_dlq_job_is_safe`: second retry rejected, exactly one dispatch, attempt history reset exactly once |
| Worker heartbeat reporting (fresh vs. stale) | **PASS** — `test_system_health_reports_worker_heartbeats` |
| Worker re-heartbeating under the same identity doesn't duplicate its row | **PASS** — `test_worker_heartbeat_upsert_updates_existing_row_not_duplicates` |
| Lease fields populated at claim time | **PASS** — `test_claim_records_worker_lease` |
| Stuck-looking job left alone because its worker is confirmed alive (30 min stuck, 3x past the time heuristic) | **PASS** — `test_reconciliation_lease_overrides_time_heuristic_when_worker_alive` |
| Stuck job recovered fast because its worker is confirmed dead (2 min stuck, nowhere near the time heuristic) | **PASS** — `test_reconciliation_lease_recovers_job_fast_when_worker_confirmed_dead` |
| Lease correctly falls back to time heuristic when the claiming worker has no heartbeat history | **PASS** — `test_reconciliation_falls_back_to_time_heuristic_when_worker_has_no_heartbeat_history` |
| Delivery-metrics with zero data (no divide-by-zero, correct nulls) | **PASS** — `test_delivery_metrics_empty_state` |
| Delivery-metrics reflect a real successful delivery | **PASS** — `test_delivery_metrics_reflects_real_deliveries` |
| Delivery-metrics stuck-jobs count is live, not cached | **PASS** — `test_delivery_metrics_stuck_jobs_count` |
| Redis fully unavailable for an extended period (not just one call) | **Not tested** — see Remaining Risks |
| Database connection pool exhaustion | **Not tested** — see Remaining Risks |
| Large queue backlog / load test | **Not tested** — see Remaining Risks |

## Tests

```
Full backend suite: 259/259 passing (238 original baseline + 21 new)
  - New: tests/integration/test_reconciliation.py (10 tests total: 6 from the
    initial reconciliation work + 4 lease-specific tests)
  - New: 2 tests added to tests/integration/test_events.py / test_retry_engine.py
    (queue-dispatch-failure resilience in publish_event and enqueue_due_retries)
  - New: 3 tests added across test_dlq.py / test_admin.py (queue-dispatch-failure
    resilience in DLQ retry, bulk DLQ retry, and admin force-retry)
  - New: 1 test added to test_dlq.py (double-retry-of-same-DLQ-job safety)
  - New: 2 tests added to test_admin.py (worker heartbeat reporting + upsert
    idempotency)
  - New: 3 tests added to test_admin.py (delivery-metrics: empty state, real
    deliveries, stuck-jobs count)
```

## Verification

```
Typecheck (mypy app/):        PASS — 0 issues, 111 files
Lint (ruff, files touched):   PASS — 0 issues in every app/ and tests/ file modified
                               across all four rounds of this phase. Both new
                               migration files (0014, 0015) carry the same
                               import-ordering style finding (I001) present in
                               EVERY existing migration file 0001-0013 — confirmed
                               by running ruff against the full alembic/ directory
                               — left as-is to stay consistent with the established
                               convention rather than fixing it in isolation on the
                               new files only. As a side effect of this round's edit
                               to test_admin.py, one pre-existing baseline
                               unused-import finding in that file was also resolved
                               (not the point of the change, just a consequence of
                               reusing an already-imported name instead of
                               re-importing it locally).
Lint (ruff, full app+tests):  5 pre-existing findings remain in app/+tests/, all in
                               files NOT touched this phase (test_alerts.py,
                               test_delivery_executor.py, test_delivery_logs.py,
                               tests/conftest.py's deliberately-ordered model
                               imports) — confirmed pre-existing, not introduced.
                               Separately, pre-existing findings across every file
                               in alembic/versions/ (see above) — same story.
Full test suite:              PASS — 259/259 (SQLite, as before)
Migration:                    PASS — verified against a real PostgreSQL 16 instance
                               this round: fresh-database `alembic upgrade head`
                               (all 15 migrations, 0001-0015, applied cleanly), a
                               full `downgrade 0013` → `upgrade head` round-trip for
                               both new migrations (confirmed via `\d` that the
                               downgrade actually dropped the table/columns and the
                               re-upgrade restored them), and direct ORM-level
                               verification of the heartbeat, CAS-claim, and
                               lease-based reconciliation logic against real
                               Postgres rows with real foreign-key constraints (see
                               Database section above for full detail).
Production build:             Not re-run (frontend untouched this phase; backend has
                               no separate "build" step beyond the test/lint/typecheck
                               above)
```

## Remaining Risks

Being direct, as instructed — this is not a zero-risk system after this pass:

1. ~~Stuck-*job* detection is still a time heuristic, not a true per-job lease.~~
   **Fixed** — `DeliveryJob.claimed_by_worker_id`/`claimed_at` (migration `0015`)
   plus `reconcile_stuck_jobs`' new lease-aware detection now ties a stuck job to
   its specific claiming worker's heartbeat, recovering confirmed-dead workers'
   jobs immediately rather than waiting out a fixed time window, and never
   recovering a job whose worker is confirmed alive regardless of elapsed time.
   The original time heuristic remains as the fallback for jobs with no lease
   signal (pre-migration rows, or a worker with zero heartbeat history) — see
   Problem #7 above for the full design and its tests.
2. ~~DLQ retry / bulk-retry / admin force-retry still call `queue_client.enqueue()`
   without the same hardening as `publish_event`.~~ **Fixed** — all three now catch
   broker-dispatch failures the same way, with regression tests
   (`test_retry_dlq_job_survives_queue_dispatch_failure`,
   `test_bulk_retry_survives_partial_queue_dispatch_failure`,
   `test_force_retry_survives_queue_dispatch_failure`).
3. ~~No worker heartbeat / fleet health table.~~ **Fixed** — `worker_heartbeats`
   table + migration `0014`, populated by a background thread each real Celery
   worker process starts via `worker_process_init`, surfaced through
   `get_system_health`'s new `worker_health` field, and (as of item 1 above) also
   consumed directly by `reconcile_stuck_jobs` for per-job lease checks.
4. **Partially addressed — in-app metrics exist, but no export pipeline.**
   `get_delivery_metrics()` / `GET /admin/delivery-metrics` (Problem #8) now surface
   real delivery latency, retry rate, DLQ rate, and stuck-job counts — closing the
   "no visibility at all" version of this gap. What's still missing is
   Prometheus/OTel *export*: nothing in this codebase pushes or exposes these in a
   scrape/collector-compatible format, so an external monitoring stack still can't
   consume them without polling this admin endpoint and adapting the shape itself.
   `OTEL_EXPORTER_OTLP_ENDPOINT` remains an unused config placeholder from an
   earlier phase.
5. ~~DLQ concurrent-double-retry (reasoned through as safe, not given its own
   test).~~ **Fixed** — `test_double_retry_of_same_dlq_job_is_safe` now covers it
   directly.
6. **Not tested this pass:** sustained Redis outage (only single-call failure was
   exercised), DB connection pool exhaustion, large-backlog/load behavior, retry
   storm / concurrency-pressure protection under real load (the retry schedule's
   jitter exists and was audited, but no test drives actual concurrent volume
   through it). Also not tested: the lease mechanism's own edge cases under real
   concurrency (e.g. a worker's heartbeat thread stalling independently of the
   worker's ability to still process jobs — the two are separate threads in the
   same process, and a hang specific to the heartbeat thread alone, leaving task
   processing unaffected, could in theory cause a false "dead" verdict; considered
   unlikely given how simple the heartbeat loop is, but not proven with a test).
7. **No git repository in the uploaded archive**, so the "create a Git checkpoint
   before modifying production-facing behavior" step from the phase brief could not
   be performed as a real commit — noting this rather than silently skipping it.
   Recommend the person track this change through their normal git workflow via a
   diff/PR from these files rather than treating this as a substitute for one.
8. ~~Neither new migration was run against a real database.~~ **Fixed** —
   PostgreSQL 16 was installed in this sandbox specifically to close this gap. Both
   migrations were run for real: a fresh-database `upgrade head` through all 15
   migrations, a `downgrade`/`upgrade` round-trip for both new ones (confirmed via
   direct schema inspection, not just exit codes), and direct ORM-level exercises of
   the heartbeat, CAS-claim, and lease-reconciliation logic against real Postgres
   rows and constraints — not just SQLite. See the Database section above for full
   detail. What's still true: the pytest suite itself continues to run against
   SQLite by design (existing, pre-phase choice, not something this pass changed) —
   this round's verification was standalone scripts run once, not a new CI tier.
   If you want ongoing Postgres-backed CI, that's a separate decision about test
   infrastructure.

**Not claiming:** "100% failure-proof," "zero risk," or that all 28 sections of the
brief were exhaustively implemented. What's true: the one critical silent-loss bug
found (abandoned mid-processing jobs) is fixed and regression-tested; every
broker-dispatch-failure gap found (5 call sites total, across two rounds) is fixed
and regression-tested; DLQ duplicate-retry safety is now verified rather than
reasoned-about; worker-fleet liveness moved from an honest gap to a real,
tested feature; and both new migrations are now verified against real PostgreSQL,
not just structurally. What's still open is listed above, not glossed over.
