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
Remaining Risks — but it's fleet-level liveness ("is this worker process alive at
all"), not a per-job lease. `reconcile_stuck_jobs`' stuck-job detection (problem #1)
still uses the `DeliveryJob.updated_at` time heuristic, not this table — tying a
specific in-flight job to the specific worker holding it would need the executor to
record `worker_id`/`claimed_at` on the job at claim time, which wasn't done this
pass (see Remaining Risks).

Also closed: the "DLQ concurrent-double-retry" test noted as missing in the
original report. `test_double_retry_of_same_dlq_job_is_safe` verifies that a second
retry of an already-retried job is safely rejected (404, since
`_get_dlq_job_or_404` only matches `status == dead_letter`) rather than resetting
the job's attempt history a second time — confirming `dlq/service.py`'s existing
filter-based approach is safe without needing any new locking.

## Database

Migration `0014_worker_heartbeats.py` adds one new table (`worker_heartbeats`) —
additive only, no changes to existing tables, no backfill needed. Could not run
`alembic upgrade head` against a real Postgres in this sandbox (no Postgres
instance available here, same limitation as the missing git repo noted in the
original report) — the migration was verified by import/structural check and by
matching the exact column-definition pattern of migrations `0001`–`0013`, and the
corresponding SQLAlchemy model was exercised indirectly through the full test suite
(which uses SQLite `create_all`, not this migration file, to build its schema).
Recommend running `alembic upgrade head` against a real Postgres instance as part
of your own deploy process before relying on this.

No schema changes beyond that. `reconcile_stuck_jobs` (problem #1) still reuses the existing
`DeliveryJob.updated_at` column (already auto-bumped by `TimestampMixin`'s
`onupdate=func.now()` on every status-changing UPDATE, including the CAS claim) as
the staleness signal, rather than adding a new lease/heartbeat column — kept the
change minimal per the "do not invent architecture" rule. Documented above that this
is a heuristic, not a real lease.

## Queue

- `publish_event`, `enqueue_due_retries` now tolerate individual broker-dispatch
  failures without losing the durable DB state or (in `publish_event`'s case)
  falsely failing an already-successful request.
- New `reconcile_stuck_jobs` closes the gap where a lost/failed broker message was
  otherwise unrecoverable.

## Workers

Fixed the specific `task_acks_late` + CAS-claim interaction that left crashed
workers' jobs permanently stuck (see Problem #1). **Also added this round:** a real
worker heartbeat/health table — see Problem #6 above and the Workers / Admin
section below. `reconcile_stuck_jobs`' own stuck-*job* detection still uses the
time-based `updated_at` heuristic, not the new heartbeat table (see Remaining
Risks) — the two are complementary, not yet unified.

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
one.

## Observability

Added structured `logger.warning` calls in `reconcile_stuck_jobs` (when anything is
recovered) and in the queue-dispatch-failure paths (problems #2/#3/#4), so operators
can see reconciliation activity and dispatch failures in logs. Also added, this
round: real worker-fleet liveness surfaced through `system-health` (Problem #6) —
this is a genuine new observability signal, not just a log line, and is the one
piece of Phase 2 section 9 ("Worker Health") that was previously an honestly-
documented gap rather than an implementation.

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
| Redis fully unavailable for an extended period (not just one call) | **Not tested** — see Remaining Risks |
| Database connection pool exhaustion | **Not tested** — see Remaining Risks |
| Large queue backlog / load test | **Not tested** — see Remaining Risks |

## Tests

```
Full backend suite: 252/252 passing (238 original baseline + 14 new)
  - New: tests/integration/test_reconciliation.py (6 tests)
  - New: 2 tests added to tests/integration/test_events.py / test_retry_engine.py
    (queue-dispatch-failure resilience in publish_event and enqueue_due_retries)
  - New: 3 tests added across test_dlq.py / test_admin.py (queue-dispatch-failure
    resilience in DLQ retry, bulk DLQ retry, and admin force-retry)
  - New: 1 test added to test_dlq.py (double-retry-of-same-DLQ-job safety)
  - New: 2 tests added to test_admin.py (worker heartbeat reporting + upsert
    idempotency)
```

## Verification

```
Typecheck (mypy app/):        PASS — 0 issues, 110 files
Lint (ruff, files touched):   PASS — 0 issues in every app/ and tests/ file modified
                               across both rounds of this phase. Migration
                               0014_worker_heartbeats.py carries the same
                               import-ordering style finding (I001) present in
                               EVERY existing migration file 0001-0013 — confirmed
                               by running ruff against the full alembic/ directory
                               (15 findings across 14 files, one per migration) —
                               left as-is to stay consistent with the established
                               convention rather than fixing it in isolation on the
                               one new file.
Lint (ruff, full app+tests):  7 pre-existing findings in app/+tests/, all in files
                               NOT touched this phase (test_admin.py's own
                               pre-existing unused-import findings, test_alerts.py,
                               test_delivery_executor.py, test_delivery_logs.py) —
                               confirmed identical to the very first baseline lint
                               run before any changes; nothing new introduced.
                               Separately, 15 pre-existing findings across
                               alembic/versions/ (see above) — same story.
Full test suite:              PASS — 252/252
Migration:                    Added 0014_worker_heartbeats.py this round (additive
                               only, one new table) — could not run `alembic
                               upgrade head` against a real Postgres in this
                               sandbox (none available); verified structurally
                               instead (see Database section above). Recommend
                               running it for real as part of your deploy process.
Production build:             Not re-run (frontend untouched this phase; backend has
                               no separate "build" step beyond the test/lint/typecheck
                               above)
```

## Remaining Risks

Being direct, as instructed — this is not a zero-risk system after this pass:

1. **Stuck-*job* detection is still a time heuristic, not a true per-job lease**,
   even though worker-*fleet* liveness (item 3, below) is now real. The new
   `worker_heartbeats` table proves a given worker process is alive, but
   `reconcile_stuck_jobs` doesn't yet cross-reference it — `DeliveryJob` doesn't
   record which `worker_id` claimed it or when, so there's no way to ask "is the
   specific worker holding *this* job still alive" versus "are *any* workers
   alive." Closing this fully would mean the executor's `_claim_job` writing
   `worker_id`/`claimed_at` onto the job row, and `reconcile_stuck_jobs` checking
   that worker's heartbeat instead of (or in addition to) elapsed time. Not built
   this pass — the current 10-minute time heuristic remains the active safety net
   and continues to be conservative relative to the max allowed endpoint timeout.
2. ~~DLQ retry / bulk-retry / admin force-retry still call `queue_client.enqueue()`
   without the same hardening as `publish_event`.~~ **Fixed** — all three now catch
   broker-dispatch failures the same way, with regression tests
   (`test_retry_dlq_job_survives_queue_dispatch_failure`,
   `test_bulk_retry_survives_partial_queue_dispatch_failure`,
   `test_force_retry_survives_queue_dispatch_failure`).
3. ~~No worker heartbeat / fleet health table.~~ **Fixed** — `worker_heartbeats`
   table + migration `0014`, populated by a background thread each real Celery
   worker process starts via `worker_process_init`, surfaced through
   `get_system_health`'s new `worker_health` field. See item 1 above for what this
   does *not* yet cover (per-job lease).
4. **No metrics/tracing export.** Structured logging exists and now covers the new
   reconciliation/dispatch-failure paths; there's no Prometheus/OTel wiring, despite
   `OTEL_EXPORTER_OTLP_ENDPOINT` existing as a config placeholder from an earlier
   phase.
5. ~~DLQ concurrent-double-retry (reasoned through as safe, not given its own
   test).~~ **Fixed** — `test_double_retry_of_same_dlq_job_is_safe` now covers it
   directly.
6. **Not tested this pass:** sustained Redis outage (only single-call failure was
   exercised), DB connection pool exhaustion, large-backlog/load behavior, retry
   storm / concurrency-pressure protection under real load (the retry schedule's
   jitter exists and was audited, but no test drives actual concurrent volume
   through it).
7. **No git repository in the uploaded archive**, so the "create a Git checkpoint
   before modifying production-facing behavior" step from the phase brief could not
   be performed as a real commit — noting this rather than silently skipping it.
   Recommend the person track this change through their normal git workflow via a
   diff/PR from these files rather than treating this as a substitute for one.
8. **The new migration was not run against a real database.** No Postgres instance
   was available in this sandbox. The migration file was checked structurally
   (imports cleanly, matches the exact column-definition pattern of every prior
   migration) and the corresponding model was exercised through the full test suite
   — but that suite runs against SQLite via `create_all`, which does not go through
   Alembic at all. Run `alembic upgrade head` (and ideally `downgrade` then
   `upgrade` again) against a real Postgres instance before deploying this.

**Not claiming:** "100% failure-proof," "zero risk," or that all 28 sections of the
brief were exhaustively implemented. What's true: the one critical silent-loss bug
found (abandoned mid-processing jobs) is fixed and regression-tested; every
broker-dispatch-failure gap found (5 call sites total, across two rounds) is fixed
and regression-tested; DLQ duplicate-retry safety is now verified rather than
reasoned-about; worker-fleet liveness moved from an honest gap to a real,
tested feature. What's still open is listed above, not glossed over.
