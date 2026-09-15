# RelayHub Observability

What already exists, what this phase added, and how an operator actually
uses it. Written from the real implementation, not aspirationally -- every
claim here was checked against the code (or, for the two items marked
NOT VERIFIED, honestly flagged as not checked against live production).

---

## Health endpoints

| Endpoint | Purpose | Checks | Cost |
|---|---|---|---|
| `GET /health/live` | Liveness -- "is this process alive" | Nothing (`{"status": "ok"}` unconditionally) | Free |
| `GET /health/ready` | Readiness -- "can this instance safely serve traffic" | PostgreSQL (`SELECT 1`), Redis (`PING`), each with a 2s timeout | Two cheap round-trips, on-demand only (not on every request) |
| `GET /metrics` | Prometheus scrape target | N/A | See "Metrics" below |

Liveness deliberately never depends on Postgres or Redis -- a database
outage should make the instance report "not ready" (so a load balancer
stops sending it traffic), not "dead" (which would trigger a container
restart that can't fix a database outage and would just cause churn).
Readiness returns `503` with a per-dependency breakdown
(`{"status": "not_ready", "dependencies": {"database": {...}, "redis": {...}}}`)
when either check fails -- machine-readable, no credentials, no tenant data.

**REQUIRES MANUAL ACTION (carried over from Phase 2, still true)**: Render's
service-level `healthCheckPath` is not configured to point at either of
these -- the Dockerfile's own `HEALTHCHECK` directive uses `/health/live`
for container-level checks, but Render's platform-level check isn't wired to
either endpoint. No tool available in this environment can change that
setting; set it in the Render dashboard under this service's Settings.

## Metrics (`GET /metrics`, Prometheus text format)

Two kinds, on the same endpoint, for different reasons -- see
`app/core/metrics.py`'s module docstring for the full design rationale.
Summary:

**HTTP-level** (accumulated in-process as real traffic is served, via
`prometheus_fastapi_instrumentator`): request count, latency, in-progress
requests, by route/method/status.

**Reliability gauges** (re-derived from a live DB query on every scrape,
not accumulated -- because the processes that generate the underlying
events, like Celery workers, don't serve HTTP and can't be scraped
themselves):

| Metric | What it tells you |
|---|---|
| `relayhub_queue_depth{status=...}` | How many delivery jobs are in each state right now (`queued`, `processing`, `retrying`, `dead_letter`) |
| `relayhub_deliveries_last_hour{outcome=...}` | Terminal outcomes (`success`/`failed`) in the last hour |
| `relayhub_workers_healthy` / `relayhub_workers_unhealthy` | Worker fleet liveness, from heartbeat rows (stale after 90s) |
| `relayhub_delivery_latency_avg_ms` / `_p95_ms` | Successful-delivery latency over the metrics window |
| `relayhub_retry_rate` / `relayhub_dlq_rate` | Fraction of completed deliveries that needed a retry / ended up dead-lettered |
| `relayhub_stuck_jobs_count` | Jobs in `processing` past the 10-minute stuck-job threshold -- **nonzero and non-transient is worth alerting on** |
| `relayhub_realtime_connections` | Currently open SSE streams |
| `relayhub_realtime_events_published_total{status=...}` / `relayhub_realtime_publish_failures_total` | Realtime delivery-status notifications; a publish failure never affects the delivery itself (see "Realtime resilience" below) |
| `relayhub_insights_anomalies_last_hour`, `relayhub_insights_incidents_open{status=...}`, `relayhub_insights_rca_generated_last_hour{source=...}` | AI/deterministic anomaly-detection layer |

**Added this phase:**

| Metric | What it tells you |
|---|---|
| `relayhub_celery_task_failures_total{task_name=...}` | Celery tasks that raised an *unexpected* exception -- a real bug, not a classified delivery failure (those are tracked separately as business outcomes above, not errors) |
| `relayhub_db_pool_checked_out` / `relayhub_db_pool_size` | SQLAlchemy connection pool utilization for the API process (per-process; each Celery worker has its own short-lived pool per task, not tracked here -- see `docs/RELIABILITY.md`'s fresh-engine-per-task note) |

**Cardinality**: every label above is a small, bounded enum (status names,
outcome names, `source`). No delivery ID, event ID, request ID, tenant ID,
or raw URL is ever used as a metric label -- for tenant-specific
investigation, use logs (below) or a direct, tenant-scoped database query
via the admin API, not metrics.

## Structured logging (added this phase)

**Before this phase**: every module already logged operationally useful
lines (`logger.info("delivery_job=%s finished with status=%s", ...)`), but
Python's logging module itself was never configured -- everything fell
through to the interpreter's unconfigured default, plain text, no
consistent structure, no request correlation unless a call site manually
interpolated it (most didn't).

**Now**: `app/core/logging_config.py` configures every process (API on
startup, each Celery worker child process via `worker_process_init` --
same lifecycle as the existing tracing/heartbeat setup) to emit one JSON
object per log line: `timestamp`, `level`, `logger`, `message`, plus any
extra fields the call site passed via `extra={...}`, plus (automatically,
for every log line, from any call site, without threading a `Request`
object through) `request_id` when one is active.

**How correlation actually reaches your logs**: `RequestIDMiddleware`
(`app/middleware/request_id.py`) sets a `contextvars.ContextVar` for the
duration of each request. Because it's a contextvar (not a plain module
global), this is automatically isolated per concurrent request -- two
requests being handled at the same moment on the same event loop never see
each other's ID (there's a regression test proving exactly this:
`tests/unit/test_logging_config.py::test_concurrent_requests_do_not_leak_request_id`).
A `logging.Filter` reads that contextvar and stamps it onto every
`LogRecord` a handler processes, so any log line emitted while handling a
request -- including from deeply nested code with no access to the
request -- gets `request_id` attached for free.

**Client-supplied request IDs**: if a caller sends `X-Request-ID`, it's
echoed back and used for correlation *if and only if* it matches
`^[A-Za-z0-9_.:-]{1,128}$` (added this phase -- previously any string was
trusted verbatim, including one containing a newline, which could have
injected a fake log line into structured log output, or an unbounded
length, which would have bloated every log line for the request). A
malformed or oversized value is silently replaced with a generated UUID
instead of rejected -- the request still succeeds, it just gets an ID we
generated rather than one the caller wanted.

**For background/worker code**, `set_job_context(**fields)` /
`reset_job_context(token)` provide the same contextvar mechanism for
tagging a unit of work (e.g. `job_id`, `worker_id`) without a Request object
-- not applied retroactively to every existing Celery task in this phase
(the brief explicitly says not to rewrite every log statement); available
for whoever adds the next one.

**Security**: never logged, by convention and by construction -- API keys,
passwords, JWTs, Stripe secrets, webhook signing secrets, `DATABASE_URL`,
`Authorization` headers, cookies, raw webhook payloads. Spot-checked the
existing hot-path log call sites (`delivery/executor.py`, `workers/tasks.py`,
`dlq/service.py`) during this phase's audit -- all already log IDs and
status, never payloads or secrets. `JsonFormatter` doesn't introduce any new
risk here: it renders whatever fields a call site already chose to pass,
nothing more.

**Previously-silent gap, now fixed**: an unhandled exception (any bug that
wasn't a deliberately-caught, classified error) produced a generic `500`
response to the client -- correctly, no traceback should ever reach an API
caller -- but was **never recorded anywhere server-side either**. A real
bug behind a 500 was invisible without independently reproducing it.
`app/core/error_handlers.py`'s `unhandled_exception_handler` now calls
`logger.exception(...)` (full traceback, into the structured server-side
log only) before returning the same sanitized response as before. See
`tests/unit/test_logging_config.py::test_unhandled_exception_is_logged_and_response_has_no_traceback`.

## Distributed tracing (OpenTelemetry)

Already implemented (`app/core/tracing.py`), not touched this phase beyond
auditing it. Summary: fully wired (`opentelemetry-sdk`,
`-instrumentation-fastapi`, and an OTLP HTTP exporter), with **explicit,
hand-written trace-context propagation across the Celery queue boundary**
(`queue_client.py` injects on enqueue, `tasks.py` extracts in the worker) --
this matters because FastAPI and Celery's own auto-instrumentation don't
connect to each other by default, and the actual valuable trace here is
"this `publish_event` request caused *this* `deliver_webhook` task, which
ran in a different process." Entirely disabled (true no-op, zero overhead,
no attempted connection to a collector) whenever
`OTEL_EXPORTER_OTLP_ENDPOINT` is unset, which is the default everywhere
including this test suite and local dev.

Audited this phase for gaps in the boundary list this document's Phase 3
brief asked about (API request → event creation → delivery creation → queue
submission → Celery worker → delivery attempt → retry → realtime
publication): the queue-submission → worker boundary is the one that
actually needs hand-written propagation (confirmed present, above); the
rest are ordinary function calls within one process and are already covered
by the FastAPI/Celery task auto-instrumentation once tracing is configured.
No gap found worth closing this phase.

## Retry / DLQ observability

Already comprehensive (`docs/RELIABILITY.md` covers the full lifecycle in
detail; this section is the metrics/logs view specifically). An operator
can distinguish temporary vs. permanent-destination vs. internal-processing
failure via `delivery_attempts.error_category`
(`transient_http_error` / `timeout` / `connection_error` = temporary,
`permanent_http_error` = destination said no and meant it,
`ssrf_blocked` / `signing_error` = internal). `relayhub_retry_rate` and
`relayhub_dlq_rate` give the aggregate view; `relayhub_queue_depth{status="retrying"}`
and `{status="dead_letter"}` give the current backlog. DLQ replay is a
manual, audited action (`POST /v1/dlq/{id}/retry`) -- there's no automatic
replay, by design (see `docs/RELIABILITY.md`).

## Stuck job detection

`relayhub_stuck_jobs_count` (a job in `processing` past 10 minutes) is the
metric to alert on. Behind it: `reconcile_stuck_jobs` runs every 60 seconds
via Celery beat, using the existing `worker_heartbeats` table plus a
time-based fallback heuristic, reclaiming jobs whose claiming worker either
sent its last heartbeat too long ago or claimed the job too long ago with no
heartbeat at all (see `docs/RELIABILITY.md`'s Crash Safety section for the
full two-tier logic). This already uses indexed queries (`status`,
`claimed_by_worker_id`) -- no new index was needed or added this phase; the
composite `(status, next_attempt_at)` index from Phase 1 covers the
retry-scan path, a related but separate query.

## Celery / worker observability

Worker fleet liveness: `relayhub_workers_healthy` /
`relayhub_workers_unhealthy`, from the heartbeat table (`WORKER_HEARTBEAT_STALE_AFTER`
= 90s). **Added this phase**: `relayhub_celery_task_failures_total{task_name=...}`
-- previously, an unexpected exception escaping a Celery task was only
visible via Celery's own internal state, not through this codebase's
metrics or structured logs. A `task_failure` signal handler
(`app/workers/celery_app.py`) now increments the counter and logs a
structured line (task name, task ID, exception class -- never the
exception's own message or args, which could in principle contain
task-argument data) for any task that fails this way.

No new queue system, no RabbitMQ, no change to the Redis/Celery
architecture -- observability only.

## Redis observability

Audited for the specific property Phase 3 asked about: **realtime Redis
failure must never corrupt or roll back durable delivery state.** Already
true and already tested: `emit_delivery_update`
(`app/modules/realtime/events.py`) wraps its publish call in
`try/except Exception`, logs and counts the failure
(`relayhub_realtime_publish_failures_total`), and never re-raises --
delivery/retry/DLQ state is committed to Postgres before that call runs,
by construction. `tests/unit/test_worker_task_realtime_lifecycle.py`
(from PR #19) already regression-tests the specific event-loop-safety bug
this exact area once had (a cached, loop-bound Redis client reused across
Celery's per-task `asyncio.run()` boundaries) -- not re-tested here since
that coverage already exists and still passes.

## PostgreSQL observability

`relayhub_db_pool_checked_out` / `relayhub_db_pool_size` (added this
phase) expose the API process's SQLAlchemy pool utilization -- a rising
`checked_out` approaching `size` is the leading indicator of pool
exhaustion before it actually happens. Reads directly from SQLAlchemy's
own in-process pool counters (`pool.checkedout()`, `pool.size()`) --
no query, no I/O, safe to compute on every scrape. Skips cleanly (no
gauge update, no error) on SQLite's `StaticPool`, which has neither method
-- relevant for local dev/tests, not production (which always uses
`QueuePool`, since `DATABASE_URL` is Postgres).

Connection failures themselves surface through `/health/ready` (see
above) and through normal exception logging (an operation that fails
because the pool is exhausted or the DB is unreachable raises, and now
gets logged with a traceback via the same `unhandled_exception_handler`
fix described above, if it isn't already caught more specifically
upstream).

## Error classification

`app/core/error_handlers.py` already distinguishes `HTTPException` (business/
validation/auth errors -- status code and message reflect the real cause,
e.g. `429` "rate_limited", `403` "forbidden"), `RequestValidationError`
(structured Pydantic field-level detail), and everything else (`Exception`
-- generic "An unexpected error occurred" to the client, full traceback
server-side only, per the fix above). No internal stack trace has ever
been exposed to an API client in this codebase -- confirmed by reading
`unhandled_exception_handler`'s response body construction, unchanged by
this phase's fix (only the *logging* was missing, not the client-facing
sanitization).

## Realtime resilience (frontend)

Audited `apps/web/lib/realtime.ts` -- already handles everything Phase 3
asked about, no changes needed: explicit reconnect (not relying on
`EventSource`'s native retry, which would keep using an increasingly stale
access token after the first 15-minute rotation), exponential backoff
(1s → 30s cap, so a sustained outage doesn't create a reconnect storm),
and a reconciliation refetch from the authoritative REST API on every
successful (re)connect (since SSE delivery isn't guaranteed -- a Redis
restart, a dropped connection, or a backgrounded tab can all lose events
silently, and the UI must be able to self-heal from the database rather
than trust the stream as its only source of truth).

## Admin operations visibility

`app/(dashboard)/admin/page.tsx` already surfaces the queue-depth/
worker-health/delivery-metrics data this document describes, via the
existing `GET /v1/admin/...` JSON endpoints (the same underlying
`admin/operations.py` functions this phase's Prometheus gauges also read
from -- one source of truth, two presentations). Not modified this phase.
RBAC/tenant-isolation on these endpoints: unchanged, not re-audited this
phase beyond confirming no new admin surface was added.

## Incident investigation flow

```
Alert fires (see docs/operations/ALERTING.md for thresholds)
    │
    ▼
Check /health/ready — is the API itself healthy?
    │
    ▼
Check relayhub_deliveries_last_hour{outcome="failed"} and
relayhub_retry_rate / relayhub_dlq_rate — is failure/retry elevated?
    │
    ▼
Check relayhub_queue_depth{status="queued"|"retrying"} — is a backlog
building rather than draining?
    │
    ▼
Check relayhub_workers_healthy/_unhealthy and relayhub_stuck_jobs_count —
are workers actually processing the backlog?
    │
    ▼
Check relayhub_db_pool_checked_out vs _size, and Redis reachability
(GET /health/ready's "redis" dependency) — is an infrastructure
dependency the bottleneck?
    │
    ▼
Search structured logs by request_id (API-originated) or by the relevant
delivery_job_id/organization_id/endpoint_id (already present in existing
delivery-path log lines — see workers/tasks.py, delivery/executor.py) to
find the specific failing operation and its traceback if it's a bug
    │
    ▼
Identify the affected endpoint/tenant from the delivery_jobs/delivery_attempts
rows the logs point at (GET /v1/deliveries/{id}, GET /v1/dlq, or a direct
tenant-scoped admin query — never cross-tenant, see tenant isolation notes
throughout docs/RELIABILITY.md)
    │
    ▼
Recover: see docs/RELIABILITY.md (retry/DLQ mechanics) and
docs/operations/DATABASE_RECOVERY.md (if the incident is DB-level)
    │
    ▼
Verify recovery: relayhub_queue_depth draining, relayhub_stuck_jobs_count
back to zero, relayhub_workers_healthy at expected count, new deliveries
succeeding
```

## Known limitations

- Structured JSON logs are not yet shipped anywhere queryable beyond
  whatever the hosting platform's own log viewer provides (Render's log
  tab) -- no log aggregation service (e.g. a hosted Loki/Elasticsearch) is
  configured. This is consistent with the rest of this project's
  "avoid unnecessary new infrastructure" principle; revisit if/when log
  volume or investigation frequency justifies it.
- In-process Counters (Celery task failures, AI call metrics, most of the
  realtime counters) reflect only the specific process that gets scraped --
  with multiple Celery worker processes, per-worker failure counts aren't
  summed cluster-wide without either scraping each worker individually
  (which would need each to expose its own HTTP endpoint -- new
  infrastructure, not added) or a push-gateway (same). Documented tradeoff,
  not an oversight -- see `app/core/metrics.py`'s module docstring for the
  full reasoning, which predates this phase and applies equally to the
  Celery task-failure counter this phase added.
- Production verification of this phase's changes: **NOT VERIFIED** against
  live Render logs/metrics as of this writing -- these changes have not
  been merged/deployed yet. See the PR for what was verified locally
  (test suite, manual smoke checks) versus what still needs a real
  production observation once deployed.
