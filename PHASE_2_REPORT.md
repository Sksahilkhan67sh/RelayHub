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

## Database

No schema changes, no migration. `reconcile_stuck_jobs` reuses the existing
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
workers' jobs permanently stuck (see Problem #1). Did **not** build a worker
heartbeat/health table this pass — see Remaining Risks.

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

Concurrent-double-retry-from-DLQ was reasoned through (both concurrent admin retries
succeed harmlessly at the DB level, and the resulting duplicate broker message is
absorbed by the executor's CAS claim same as any other duplicate enqueue) but not
given its own explicit test — see Remaining Risks.

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

## Security

Not re-run as a full regression pass this phase (the audit report from the prior
phase already covers tenant isolation broadly). Spot-checked that
`reconcile_stuck_jobs` and its new Celery task operate cluster-wide by design (it's
an internal maintenance task with no tenant-scoped API surface, no user input, and
no new route) — there is no new attack surface introduced by this phase's changes.

## Observability

Added structured `logger.warning` calls in `reconcile_stuck_jobs` (when anything is
recovered) and in the queue-dispatch-failure paths (problems #2/#3), so operators
can see reconciliation activity and dispatch failures in logs. Did **not** add new
Prometheus/OTel metrics — `OTEL_EXPORTER_OTLP_ENDPOINT` exists as an unused config
setting from before this phase; no metrics-export instrumentation exists anywhere in
this codebase yet, and wiring one up from scratch was judged out of scope for a
reliability-focused pass with an already very large surface. This is a real,
documented gap, not a silent omission.

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
| Redis fully unavailable for an extended period (not just one call) | **Not tested** — see Remaining Risks |
| Database connection pool exhaustion | **Not tested** — see Remaining Risks |
| Large queue backlog / load test | **Not tested** — see Remaining Risks |

## Tests

```
Full backend suite: 249/249 passing (238 original baseline + 11 new)
  - New: tests/integration/test_reconciliation.py (6 tests)
  - New: 2 tests added to tests/integration/test_events.py / test_retry_engine.py
    (queue-dispatch-failure resilience in publish_event and enqueue_due_retries)
  - New: 3 tests added across test_dlq.py / test_admin.py (queue-dispatch-failure
    resilience in DLQ retry, bulk DLQ retry, and admin force-retry)
```

## Verification

```
Typecheck (mypy app/):        PASS — 0 issues, 110 files
Lint (ruff, files touched):   PASS — 0 issues in every file modified this phase,
                               including this follow-up pass (dlq/service.py,
                               admin/service.py, test_dlq.py)
Lint (ruff, full app+tests):  7 pre-existing findings, all in files NOT touched this
                               phase (test_admin.py's own pre-existing unused-import
                               findings, test_alerts.py, test_delivery_executor.py,
                               test_delivery_logs.py) — confirmed identical to the
                               very first baseline lint run before any changes;
                               nothing new introduced, including in this follow-up
Full test suite:              PASS — 249/249
Migration:                    N/A — no schema change this phase
Production build:             Not re-run (frontend untouched this phase; backend has
                               no separate "build" step beyond the test/lint/typecheck
                               above)
```

## Remaining Risks

Being direct, as instructed — this is not a zero-risk system after this pass:

1. **Stuck-job detection is a time heuristic, not a true lease.** Without a
   per-attempt worker heartbeat, `reconcile_stuck_jobs` can only infer "probably
   abandoned" from elapsed time. The 10-minute threshold is deliberately
   conservative relative to the max allowed endpoint timeout, but a genuinely
   pathological hang could still theoretically cause a duplicate attempt. A real
   lease (worker writes a heartbeat row/column it renews while processing) would
   close this fully; not built this pass.
2. ~~DLQ retry / bulk-retry / admin force-retry still call `queue_client.enqueue()`
   without the same hardening as `publish_event`.~~ **Fixed in a follow-up pass** —
   all three now catch broker-dispatch failures the same way, with regression tests
   (`test_retry_dlq_job_survives_queue_dispatch_failure`,
   `test_bulk_retry_survives_partial_queue_dispatch_failure`,
   `test_force_retry_survives_queue_dispatch_failure`).
3. **No worker heartbeat / fleet health table.** `admin/service.py`'s
   `get_system_health` still honestly reports "not tracked" rather than fabricating
   worker-health data — this phase didn't change that. Building it needs a new
   table + migration + a periodic heartbeat write from the worker process, which is
   a real, non-trivial addition better scoped as its own follow-up.
4. **No metrics/tracing export.** Structured logging exists and now covers the new
   reconciliation/dispatch-failure paths; there's no Prometheus/OTel wiring, despite
   `OTEL_EXPORTER_OTLP_ENDPOINT` existing as a config placeholder from an earlier
   phase.
5. **Not tested this pass:** sustained Redis outage (only single-call failure was
   exercised), DB connection pool exhaustion, large-backlog/load behavior, retry
   storm / concurrency-pressure protection under real load (the retry schedule's
   jitter exists and was audited, but no test drives actual concurrent volume
   through it), and DLQ concurrent-double-retry (reasoned through as safe, not
   given its own test).
6. **No git repository in the uploaded archive**, so the "create a Git checkpoint
   before modifying production-facing behavior" step from the phase brief could not
   be performed as a real commit — noting this rather than silently skipping it.
   Recommend the person track this change through their normal git workflow via a
   diff/PR from these files rather than treating this as a substitute for one.

**Not claiming:** "100% failure-proof," "zero risk," or that all 28 sections of the
brief were exhaustively implemented. What's true: the one critical silent-loss bug
found (abandoned mid-processing jobs) is fixed and regression-tested; two related
dispatch-failure gaps are fixed and regression-tested; everything else audited was
either already correct or is listed above as a genuine, undone gap.
