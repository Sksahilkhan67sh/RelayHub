# CI Root Cause Analysis — RelayHub

Method: since raw logs were unreachable (see `CI_FAILURE_INVENTORY.md`), each job's exact CI command was reproduced directly against current `main` — locally where possible (backend against real PostgreSQL 16 + Redis, matching CI's service containers), and via a real GitHub Actions run for the two jobs the sandbox couldn't run at all (Maven/Java, Docker). For the one cluster that couldn't be reproduced (because it doesn't recur), job-level telemetry (runner assignment, timing, `needs:` graph) was used as evidence instead, and GitHub's public status history was checked for corroboration.

| Root Cause Group | Runs Affected | Current Main | Reproducible | Fix Required | Status |
|---|---:|---|---|---|---|
| backend — sqlite tests | 101 | Passing (402/402) | No (passes cleanly, verified 3x) | No | HISTORICAL — ALREADY FIXED |
| frontend — Typecheck | 45 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| backend-postgres — Tests | 37 | Passing (402/402 vs real Postgres+Redis) | No | No | HISTORICAL — ALREADY FIXED |
| backend — Lint (ruff) | 26 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| backend-postgres — alembic migrations | 25 | Passing (clean upgrade head) | No | No | HISTORICAL — ALREADY FIXED |
| java-sdk — mvn compile test | 19 | Passing (real GitHub runner, before and after PR #1) | No | No | HISTORICAL — ALREADY FIXED |
| python-sdk — pytest | 16 | Passing (24/24) | No | No | HISTORICAL — ALREADY FIXED |
| node-sdk — npm build | 16 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| go-sdk — go build | 16 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| cli — tsc | 12 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| backend — Typecheck (mypy) | 5 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| docker-build — validate compose | 3 | Passing (real runner) | No | No | HISTORICAL — ALREADY FIXED |
| python-sdk — mypy | 1 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| go-sdk — go test | 1 | Passing | No | No | HISTORICAL — ALREADY FIXED |
| Instant whole-run failure (2 bursts, 10 runs) | 10 | Not observed | No (pattern doesn't recur) | No | **UNVERIFIED — see deep-dive below** |

## Deep-dive: the 10-run "instant whole-run failure" cluster

### Affected run IDs, commits, and jobs (complete list)

**Burst 1 — 2026-08-22, 20:29:58 to 20:33:21 UTC (5 runs, ~55s apart)**

| Run ID | Commit SHA | Commit title | Failed jobs (all 0-3s, no steps run) |
|---|---|---|---|
| 32596846322 | `778cc8ef73` | Modify analytics router for dual path support | backend, frontend, node-sdk, python-sdk, go-sdk, java-sdk |
| 32596883462 | `be0c2a815b` | Mount analytics router with dual prefixes | same 6 |
| 32596930399 | `a14332d632` | Change API endpoint from /v1/analytics to /v1/insights | same 6 |
| 32596972531 | `f2fb713270` | Change API calls from analytics to insights endpoint | same 6 |
| 32597018458 | `167034f5fd` | Add tests for insights alias and OpenAPI exclusion | same 6 |

**Burst 2 — 2026-08-30, 13:36:54 to 13:40:46 UTC (5 runs, ~40-90s apart)**

| Run ID | Commit SHA | Commit title | Failed jobs |
|---|---|---|---|
| 33314656966 | `dafbf720d0` | Enhance AI provider configuration and documentation | backend, frontend, node-sdk, python-sdk, go-sdk, java-sdk, backend-postgres |
| 33314684224 | `91b193b6f7` | Update .env.example with AI provider settings | same 7 |
| 33314724202 | `3cac3ef378` | Refactor AI provider for gateway compatibility | same 7 |
| 33314784995 | `8186c854a3` | Add files via upload | same 7 |
| 33314828039 | `6fa1f925de` | Add files via upload | same 7 |

In every run, `cli` and `docker-build` show conclusion `skipped`, not `success` or `failure` — this is expected `needs:` cascade behavior (`cli` needs `node-sdk`; `docker-build` needs `[backend, frontend]`), not independent evidence of anything. They never had a chance to run.

### Evidence gathered

1. **Job-level telemetry** (from `/actions/runs/{id}/jobs`, verified for every job in every one of the 10 runs): every failed job shows `runner_id: 0`, `runner_name: ""`, `steps: []`, and `started_at`/`completed_at` 1-3 seconds apart. This means GitHub never assigned a runner to any of these jobs — they failed before "Set up job" even began, not during a step.
2. **Whole-run and check-suite status**: both report `conclusion: failure` for these runs (not `cancelled`), completing in 3 seconds for an 8-9 job matrix.
3. **Ruled out — workflow config**: `.github/workflows/ci.yml` was not modified in either burst window (checked via `git log` on that path). No `concurrency:` block exists in the workflow, so run-cancellation-on-push is not a factor.
4. **Ruled out — concurrency/capacity from overlapping runs**: the 5 runs in each burst are *sequential*, not overlapping — each completes in ~3 seconds, roughly 40-90 seconds before the next one starts. So this isn't "too many jobs queued at once."
5. **Checked — GitHub public status history**: searched for incidents on 2026-08-22 and 2026-08-30. No incident is listed for either date. The nearest documented Actions-related incidents are 2026-08-20 (8h13m outage), 2026-08-24 (13:33-14:04 UTC, runner-assignment disk failure causing some Actions runs to fail outright), and 2026-08-26 (15:02-15:45 UTC, Actions jobs failing to start due to database saturation) — none overlap the two windows in question.
6. **Checked — check-run annotations**: empty for these jobs (no error text was ever attached, consistent with the job never starting).
7. **Checked — raw log content**: unreachable (see `CI_FAILURE_INVENTORY.md`); for jobs with `runner_id: 0` there is likely no log to retrieve regardless, since no runner ever executed anything.

### Determination: UNVERIFIED

The evidence (no runner ever assigned, sub-3-second failure across every independent job simultaneously, two repeatable bursts, no workflow-file or concurrency-config explanation, no capacity-overlap explanation) is most consistent with a **transient runner-provisioning failure** on GitHub's side. However, per instruction not to guess: no public GitHub status incident corroborates either exact window, so this cannot be confirmed. It is reported as unresolved, not asserted as "transient/infrastructure," and current `main` is unaffected (all 9 jobs pass on it now, including runs made well after both burst windows).
