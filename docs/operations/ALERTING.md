# RelayHub Alerting

**Status: definitions only, not wired to a live alerting platform.** No
external alerting service (PagerDuty, Opsgenie, Grafana Alerting, etc.) is
configured in this repository or account as of this writing -- there was no
existing configuration to extend, and standing one up is a real
infrastructure/billing decision outside what this phase makes unilaterally
(consistent with this project's "no unnecessary new infrastructure without
justification" principle, and with Phase 2's precedent of not making
billing decisions without explicit confirmation). What follows is a
production-ready set of thresholds and the exact PromQL to evaluate them
against `/metrics` (see `docs/operations/OBSERVABILITY.md`) -- copy these
directly into whichever platform gets configured. **Do not treat any of
these as active until they're actually loaded into a real alerting
system.**

## Severity model

**CRITICAL** — page immediately, work stops until resolved.
**HIGH** — needs attention within the hour, not necessarily a page.
**MEDIUM** — worth investigating same-day, not urgent.

Deliberately few alerts, not one per possible failure -- a noisy alert
policy trains people to ignore alerts, which is worse than no alerting at
all. Every alert below should be actionable: if firing it wouldn't change
what an operator does next, it doesn't belong here.

---

## CRITICAL

### Application unavailable
```promql
up{job="relayhub-api"} == 0
```
Or, if scraping through a proxy that can't tell "down" from "responding
with an error": `probe_success{instance="<api>/health/live"} == 0`.
**For**: 2 minutes (avoid paging on a single missed scrape).

### Readiness failing (sustained)
```promql
probe_success{instance="<api>/health/ready"} == 0
```
**For**: 5 minutes. A brief blip during deploy is expected and shouldn't
page; five minutes of `/health/ready` returning `503` means a real,
sustained dependency outage (see the `dependencies` field in the response
body for which one).

### Database unavailable
```promql
up{job="relayhub-api"} == 1 and probe_success{instance="<api>/health/ready"} == 0
```
combined with checking `/health/ready`'s response body for
`"database": {"ok": false}` specifically (distinguishes a DB outage from a
Redis-only one, which is HIGH not CRITICAL -- see below).
**For**: 3 minutes.

### Major worker outage
```promql
relayhub_workers_healthy == 0
```
**For**: 3 minutes (heartbeats are 15s; three minutes of zero healthy
workers is unambiguous, not a blip).

### Delivery processing completely stalled
```promql
relayhub_queue_depth{status="queued"} > 0 and rate(relayhub_deliveries_last_hour[10m]) == 0
```
Jobs are queued, but nothing is completing -- distinguishes "no traffic
right now" (both sides zero, not alertable) from "traffic exists but isn't
being processed" (the actually dangerous state).
**For**: 5 minutes.

---

## HIGH

### Sustained delivery failure spike
```promql
relayhub_deliveries_last_hour{outcome="failed"} / (relayhub_deliveries_last_hour{outcome="failed"} + relayhub_deliveries_last_hour{outcome="success"}) > 0.25
```
**For**: 15 minutes. 25% is a starting point, not a measured production
baseline (this project has no real failure-rate history yet to calibrate
against, per `docs/RELIABILITY.md`'s honesty about limited current data
volume) -- revisit once real traffic establishes what "normal" looks like.

### Retry backlog growing
```promql
relayhub_queue_depth{status="retrying"} > 50 and delta(relayhub_queue_depth{status="retrying"}[30m]) > 0
```
Both conditions matter: a large-but-shrinking backlog is recovering on its
own; a small-but-growing one is the actual early warning. 50 is a starting
threshold for this project's current scale -- see the note on the failure
rate above about calibration.

### DLQ growth spike
```promql
relayhub_dlq_rate > 0.10
```
**For**: 15 minutes. 10% of completed deliveries ending up dead-lettered
is a real destination or endpoint-configuration problem, not noise.

### Stuck jobs increasing
```promql
relayhub_stuck_jobs_count > 5
```
**For**: 5 minutes. Any sustained nonzero value here means reconciliation
isn't keeping up (it runs every 60s and should normally hold this at or
near zero) -- see `docs/operations/OBSERVABILITY.md`'s stuck-job section.

### Redis outage affecting core functionality
```promql
probe_success{instance="<api>/health/ready"} == 0
```
with `/health/ready`'s body showing `"redis": {"ok": false}` and
`"database": {"ok": true}` -- Redis-only failures are HIGH, not CRITICAL,
specifically *because* of the durability boundary this codebase maintains:
a Redis outage degrades new-delivery dispatch and realtime updates, but
never corrupts or loses already-durable Postgres state (see
`docs/operations/OBSERVABILITY.md`'s Redis section). Still needs prompt
attention -- new deliveries can't be dispatched until Redis is back --
just not a "the data itself is at risk" page.

---

## MEDIUM

### Elevated latency
```promql
relayhub_delivery_latency_p95_ms > 5000
```
**For**: 15 minutes.

### Repeated reconciliation failures
No direct metric for this yet -- **NOT VERIFIED / not yet instrumented**.
`reconcile_stuck_jobs` catches and logs its own failures per-run (see
`docs/RELIABILITY.md`), but there's no dedicated counter distinguishing "a
reconciliation run itself failed" from "a reconciliation run succeeded but
found nothing to do." Until one exists, use a log-based alert instead: more
than 3 ERROR-level log lines from `app.modules.retry.reconciliation` in a
15-minute window (structured logs now make this queryable -- see
`docs/operations/OBSERVABILITY.md`). Adding a proper metric for this is
listed as follow-up work, not done this phase (a real gap, but a log-based
alert is an adequate interim signal and a new gauge/counter for a case
that -- per the reconciliation code's own design -- should essentially
never actually fire didn't seem worth the added metric surface yet).

### Unusual queue growth
```promql
delta(relayhub_queue_depth{status="queued"}[15m]) > 100
```
100 is a starting threshold for this project's current traffic volume, not
a calibrated production baseline -- revisit as real volume grows.

---

## Alert routing (not configured -- document only)

Once an actual platform is wired up:
- CRITICAL → page on-call immediately.
- HIGH → notify on-call channel, no page, expect acknowledgment within the
  hour.
- MEDIUM → ticket/backlog, reviewed same-day.

## Backup failure visibility

Separate from the above (covered in detail in
`docs/operations/DATABASE_RECOVERY.md` section 17): the scheduled backup
workflow (`.github/workflows/backup.yml`) already surfaces its own failures
via GitHub Actions' own run-history UI (a failed run shows red in the
Actions tab) plus a sanitized, actionable check-run annotation on any
`Run backup` step failure -- this was verified for real during Phase 2's
backup-execution work, not just designed. No additional alerting
infrastructure was added for this in Phase 3; GitHub's own visibility is
judged sufficient at this project's current scale, consistent with the
"no unnecessary new infrastructure" principle applied throughout.
