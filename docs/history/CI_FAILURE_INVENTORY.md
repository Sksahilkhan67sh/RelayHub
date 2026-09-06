# CI Failure Inventory — RelayHub

**Scope:** all 205 runs where the `CI` workflow (`.github/workflows/ci.yml`) concluded `failure`, out of 419 total historical runs, as of 2026-08-31.

## What could and couldn't be collected

- Run ID, commit SHA, branch, commit title, timestamp, workflow, job name, and failed step name were pulled for **all 205/205 runs** via the GitHub Actions API (`/actions/runs`, `/actions/runs/{id}/jobs`).
- **Raw failure log text could not be retrieved for any run.** GitHub redirects job-log downloads to `productionresultssa12.blob.core.windows.net` (Azure Blob Storage), which is not reachable from the sandbox this audit ran in (`x-deny-reason: host_not_allowed`). Check-run annotations were checked as a fallback but only surfaced the generic `Process completed with exit code 1.`, not the underlying error.
- Because of this, root-cause grouping below is at **(job, failed step)** granularity — the finest level verifiable without log access — not at the level of individual error messages. A single (job, step) group very likely contains multiple distinct bugs that were introduced and fixed at different times across the 3-week window, not one bug.
- In place of reading historical logs, root cause was determined by **reproducing each job's exact CI command against current `main`**, locally where possible and via a real GitHub Actions run where not (see `CI_ROOT_CAUSE_ANALYSIS.md`).

Full per-run raw data (205 records, job/step level) was saved to `CI_FAILURE_INVENTORY_RAW.json`/`jobs_raw.json` during the audit.

## Failure counts by (job, failed step)

| Job | Failed step | Runs | First occurrence | Last occurrence |
|---|---|---:|---|---|
| backend | Tests (sqlite, matches local dev) | 101 | 2026-08-12T12:02:40Z | 2026-08-31T10:15:01Z |
| frontend | Typecheck | 45 | 2026-08-13T11:18:45Z | 2026-08-28T08:51:53Z |
| backend-postgres | Tests (real PostgreSQL, not SQLite) | 37 | 2026-08-27T11:07:40Z | 2026-08-31T10:15:01Z |
| backend | Lint | 26 | 2026-08-12T12:47:41Z | 2026-08-23T19:49:02Z |
| backend-postgres | Run alembic migrations against real Postgres | 25 | 2026-08-25T09:43:24Z | 2026-08-25T10:12:40Z |
| java-sdk | Run mvn -B compile test | 19 | 2026-08-12T12:02:40Z | 2026-08-27T10:10:06Z |
| python-sdk | Run pytest -q | 16 | 2026-08-25T10:08:47Z | 2026-08-27T10:14:02Z |
| node-sdk | Run npm run build | 16 | 2026-08-27T09:57:01Z | 2026-08-27T10:12:00Z |
| go-sdk | Run go build ./... | 16 | 2026-08-27T09:52:49Z | 2026-08-27T10:08:36Z |
| cli | Run npx tsc --noEmit | 12 | 2026-08-14T06:48:29Z | 2026-08-27T09:55:34Z |
| backend | Typecheck (mypy) | 5 | 2026-08-23T19:54:52Z | 2026-08-29T18:36:39Z |
| docker-build | Validate compose files | 3 | 2026-08-12T12:51:15Z | 2026-08-31T05:39:26Z |
| python-sdk | Run mypy relayhub | 1 | 2026-08-27T09:58:10Z | — |
| go-sdk | Run go test ./... | 1 | 2026-08-20T08:04:40Z | — |
| *(6 job types simultaneously, no step recorded — job errored in ~1-3s before any step started)* | — | 10 unique runs (60 job-failure rows across backend/frontend/java-sdk/go-sdk/node-sdk/python-sdk, +5 more on backend-postgres in a subset) | 2026-08-22T20:29:58Z | 2026-08-30T13:40:46Z |

UNVERIFIED: exact error text for every group above — logs unreachable, see note above.
