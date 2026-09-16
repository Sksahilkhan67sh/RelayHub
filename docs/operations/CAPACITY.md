# RelayHub Capacity & Performance

**Read this first**: almost everything in this document is **ESTIMATED**
or **UNKNOWN**, not measured. RelayHub's production instance currently
carries a handful of events per day against a ~10MB database (see
`docs/operations/DATABASE_RECOVERY.md`) -- there is no real traffic history
to derive measured capacity numbers from, and no load-testing environment
available in the phase that produced this document. Numbers below are
labelled accordingly. **Do not cite the estimates as measurements.**

---

## Request path

```
Incoming events (HTTP POST /v1/events)
      │
      ▼
API workers (uvicorn, async)
      │
      ▼
PostgreSQL  ── event row + delivery_job row (one transaction)
      │
      ▼
Redis / Celery queue  ── enqueue after commit
      │
      ▼
Delivery workers (Celery) ── claim (CAS), HTTP POST, record attempt
      │
      ▼
External destinations  ◄── almost always the real bottleneck
```

## Configured limits (MEASURED -- read from config, not inferred)

| Component | Setting | Value |
|---|---|---|
| API DB pool | `DATABASE_POOL_SIZE` | 20 |
| API DB pool overflow | `DATABASE_MAX_OVERFLOW` | 10 |
| PostgreSQL server | `max_connections` (Render free plan) | 100 |
| Redis | plan | free, `maxmemory-policy: allkeys_lru`, **persistence off** |
| Webhook timeout | per-endpoint `timeout_seconds` | 15s default |
| Retry scan cadence | Celery beat | every 10s |
| Reconciliation cadence | Celery beat | every 60s |
| Worker heartbeat staleness | `WORKER_HEARTBEAT_STALE_AFTER` | 90s |

## Connection budget (ESTIMATED -- arithmetic, not observed)

The API pool alone can reach **30 connections per API process**
(20 + 10 overflow). Celery workers use a *fresh engine per task*, disposed
at task end (a deliberate event-loop-safety tradeoff -- see
`docs/RELIABILITY.md`), so each concurrently-executing task holds roughly
one connection for its duration rather than maintaining a long-lived pool.

Against PostgreSQL's 100-connection ceiling:

```
(API processes × 30)  +  (Celery concurrency × ~1)  +  beat  <  100
```

With one API process and modest Celery concurrency this is comfortable. **A
second or third API process is where this gets tight** -- 3 × 30 = 90
leaves almost nothing for workers. **Recommendation before scaling API
instances horizontally: lower `DATABASE_POOL_SIZE` per process rather than
raising PostgreSQL's ceiling**, since async handlers hold connections only
briefly. This was deliberately *not* changed in Phase 4 -- the current
single-instance configuration is not exhausted, and changing pool sizing
without load evidence would be exactly the speculative optimization the
brief prohibits. `relayhub_db_pool_checked_out` /
`relayhub_db_pool_size` (added Phase 3) are the metrics to watch to know
when this actually matters.

## Expected bottleneck order (ESTIMATED)

1. **External destinations.** A single slow endpoint occupies a worker for
   up to its `timeout_seconds`. With N workers, N simultaneously-slow
   destinations stall delivery throughput regardless of everything else.
   This is inherent to webhook delivery, not a RelayHub defect.
2. **Celery worker concurrency.** The next binding constraint once
   destinations are healthy.
3. **PostgreSQL connections** (see budget above) -- becomes the constraint
   when API instances scale out.
4. **Redis** -- unlikely to saturate at any plausible near-term volume, but
   note **persistence is off** on the free plan: a Redis restart can drop
   in-flight queue messages. Reconciliation recovers jobs that reached a DB
   row; see `docs/RELIABILITY.md`.
5. **API process CPU** -- the least likely constraint; handlers are async
   and I/O-bound.

## Query efficiency (audited Phase 4)

Hot paths were read for N+1 patterns and index coverage:

- **Delivery detail** (`delivery/query_service.get_delivery_job`) uses
  `selectinload` on attempts/event/endpoint -- no N+1.
- **Retry scanner** (`retry/scheduler.enqueue_due_retries`) filters
  `status = 'retrying' AND next_attempt_at <= now`, covered by the
  composite index `ix_delivery_jobs_status_next_attempt_at` added in
  Phase 1.
- **Reconciliation** uses the `status` and `claimed_by_worker_id` indexes.
- **Idempotency** relies on the unique constraint
  `(organization_id, idempotency_key)` -- an index lookup, not a scan.

**No new index was added in Phase 4.** The audit did not find a query whose
plan justified one, and the brief explicitly prohibits adding indexes
blindly.

**Pagination**: list endpoints use bounded `limit`/`offset`. Deep-OFFSET
scanning is a real theoretical concern at high row counts, but with the
current data volume there is no evidence it's a problem, and converting to
keyset pagination would be an API-compatibility change affecting the
frontend, SDKs, and CLI. **Deliberately deferred** -- documented as a known
consideration rather than speculatively changed. Revisit when any tenant's
`delivery_jobs` row count reaches a scale where `EXPLAIN` shows it
mattering.

## Phase 4 performance impact

**NOT MEASURED.** No load test was run (no suitable environment; see the
opening note). Reasoned analysis of what changed:

| Change | DB queries | Redis ops | Notes |
|---|---|---|---|
| DLQ replay/bulk-replay/export rate limits | unchanged | **+1 sliding-window check per call** on three endpoints | Not on the delivery hot path. These are operator-initiated, low-frequency endpoints, and the check is the same mechanism already used on event ingestion. |
| Dependency upgrades (PyJWT, cryptography, python-multipart, fastapi) | unchanged | unchanged | No code change; verified by full test suite passing on both SQLite and real PostgreSQL. |

No change to event ingestion, delivery creation, queue submission, worker
execution, retry scheduling, or realtime publication -- the six paths the
brief identifies as performance-sensitive.

## What would need measuring before claiming real capacity

- Sustained event-ingestion throughput (events/sec) at a known latency
  percentile.
- Delivery throughput per worker against a controlled, fast test
  destination.
- Behavior under a retry storm (many simultaneous `retrying` jobs).
- Connection-pool utilization under concurrent API load.
- Memory growth over a long-running worker process.

None of these have been performed. **UNKNOWN** until they are.
