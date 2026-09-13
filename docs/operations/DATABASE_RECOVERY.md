# RelayHub Database Recovery Runbook

Audience: an engineer who did not build RelayHub, responding to a database
incident. Read this top to bottom before touching anything.

Last verified: 2026-09-13, during Phase 2 (database disaster recovery
hardening). Every claim below is either evidence-backed (marked VERIFIED,
with what was actually checked) or explicitly flagged as not yet true
(NOT VERIFIED / REQUIRES MANUAL ACTION). Do not upgrade a NOT VERIFIED claim
to VERIFIED without actually doing the thing.

---

## 0. Current production database

- Name: `relayhub-db-user` (Render Postgres instance id `dpg-daifi0h594qs738i36t0-a`)
- Plan: **free** -- VERIFIED via the Render API. Free-tier Postgres on Render
  has **no automated backups and no point-in-time recovery (PITR)**. This is
  a plan limitation, not a configuration you can enable.
- Region: Singapore. Version: PostgreSQL 18.
- **Lifecycle risk**: free-tier Render Postgres instances expire (this
  exact thing already happened once -- the previous production database,
  `relayhub-db`, was suspended on 2026-09-11 for exactly this reason, which
  is why `relayhub-db-user` exists). Current `expiresAt`: **2026-10-12**.
  This is not a one-time risk -- it recurs on every free-tier database
  unless upgraded to a paid plan before expiry.
- Size as of this writing: ~10MB, ~70 rows total across all tables. Small
  enough that a full logical extraction (not just a sampled check) is
  practical -- see section 4.

## 1. Incident detection

Signs of a database incident:
- Render dashboard shows the Postgres instance as `suspended` or
  unreachable (this is exactly what happened to the previous database --
  check the Render dashboard's Postgres list first, not just the web
  service).
- `GET /health/ready` on the backend service returns 503 (it checks DB
  connectivity -- see `app/main.py`).
- Application logs show connection errors / `OperationalError` /
  `ConnectionRefusedError` from `asyncpg`.
- Celery beat's `check_due_retries` / `reconcile_stuck_jobs` tasks stop
  logging their normal every-10s / every-60s success lines.

## 2. Severity assessment

| Situation | Severity | Why |
|---|---|---|
| DB unreachable, but exists and is not suspended/deleted | Medium -- likely transient (Render incident, network) | No data at risk yet |
| DB suspended (free-tier expiry or billing) | High | Data inaccessible until either it's un-suspended (if within Render's grace window) or a new DB is built from backup |
| DB deleted / expired past Render's retention | Critical | Only recovery path is the most recent backup artifact (see section 4) -- accept the RPO gap honestly, don't pretend otherwise |
| Schema corruption / bad migration applied | Medium-High | Usually recoverable via `alembic downgrade` if the migration is reversible; check the migration file before downgrading (see section 6) |

## 3. Stop / continue decision

- If the API is still serving reads/writes against a healthy DB and this is
  a "we're worried" drill, not an active incident: **do not touch
  production**. Practice against a restore-drill environment instead (see
  section 5) -- exactly as this runbook's evidence was gathered.
- If the DB is actually down: confirm severity (section 2) before deciding
  whether to fail over to a restore or wait for Render to resolve a
  transient issue. A restore is a bigger, riskier action than waiting a few
  minutes for a transient outage to clear -- don't reach for it first.

## 4. Backup selection

**Current backup capability: REQUIRES MANUAL ACTION.** As of this writing,
there is no automated backup running against production. This phase added
`.github/workflows/backup.yml`, a scheduled (daily, 03:17 UTC) GitHub
Actions workflow that runs `scripts/backup_db.sh` (a `pg_dump --format=custom`
wrapper) and uploads the result as a 35-day-retention build artifact --
**but it does nothing until a repository owner adds a `BACKUP_DATABASE_URL`
secret** (Settings -> Secrets and variables -> Actions, plain
`postgresql://...` form, not `+asyncpg`). Until that secret exists, treat
backup capability as: **AVAILABLE (manual only, via `scripts/backup_db.sh`
run by hand) / NOT AUTOMATED**.

To take a manual backup right now, from a machine with network access to
Render's Postgres (this sandbox's own network egress does not have that
access -- see section 8):

```bash
DATABASE_URL="postgresql://<user>:<password>@<host>:5432/<db>" ./scripts/backup_db.sh ./backups
```

To select a backup for restore: once the scheduled workflow is running,
download the desired run's artifact from the Actions tab (Actions ->
"Database Backup" -> pick a run -> Artifacts). Artifacts expire after 35
days -- if you need one older than that, it's gone; this is the real
retention window, not a target.

## 5. Restore process

**Never restore into the production database directly.** Always restore
into a new, isolated instance first, verify it (section 6-7), and only then
decide how to bring it into service.

```bash
# 1. Create a fresh, empty Postgres instance (Render dashboard, or a local
#    one for a drill -- this is exactly what Phase 2's restore drill used).
# 2. Restore:
pg_restore --clean --if-exists --no-owner --dbname="postgresql://<user>:<password>@<new-host>:5432/<db>" /path/to/relayhub-TIMESTAMP.dump
# 3. Verify (section 6) BEFORE pointing any application traffic at it.
```

`scripts/restore_db.sh` wraps this same command.

**What was actually verified in this environment (Phase 2, 2026-09-13):**
this sandbox cannot open a direct network connection to any Render-hosted
Postgres instance (Render's `*.render.com` hosts are not in this
environment's network allowlist -- only the Render API's own
`query_render_postgres` tool is reachable, which executes one read-only SQL
statement per call and cannot run `pg_dump`/`pg_restore` or host a live
application connection). Because of that constraint, the actual restore
drill performed here used a **logical, evidence-preserving substitute**:
production's full row-level data (all ~70 rows across every populated
table) was extracted via `query_render_postgres` and loaded into a
freshly-migrated **local** PostgreSQL 16 instance using the application's
own SQLAlchemy models (so every custom column type -- JSON, string-list
columns -- serialized exactly as the app itself would write it). This is
**not equivalent to a real `pg_dump`/`pg_restore` cycle** and should not be
described as one; it proves the same things (schema/data/FK integrity, real
application queries succeeding against restored data) but does not exercise
`pg_dump`'s own binary format or `pg_restore`'s tooling. **A true
`pg_dump`/`pg_restore` drill from an environment with real network access
to Render has NOT been performed and is NOT VERIFIED.** Re-run this drill
for real once the `BACKUP_DATABASE_URL` secret exists and a real `.dump`
artifact is available.

## 6. Data integrity verification after restore

Run these against the restored instance before trusting it:

```sql
-- Migration version matches what production was on:
SELECT version_num FROM alembic_version;

-- Table count matches (33 as of Phase 2, including alembic_version):
SELECT count(*) FROM information_schema.tables WHERE table_schema='public';

-- FK integrity spot-checks:
SELECT count(*) FROM delivery_jobs dj JOIN events e ON dj.event_id = e.id;
SELECT count(*) FROM delivery_attempts a JOIN delivery_jobs dj ON a.delivery_job_id = dj.id;

-- Status distribution sanity check (compare to what you expect from the
-- incident timing):
SELECT status, count(*) FROM delivery_jobs GROUP BY status;

-- The retry-scan index (migration 0020) exists:
SELECT indexname FROM pg_indexes WHERE tablename='delivery_jobs' AND indexname LIKE '%next_attempt%';
```

Phase 2's drill (see section 5) ran exactly these checks against the
restored local instance and got an **exact** match against production's
live counts at extraction time: 1 organization, 1 user, 1 membership, 1 API
key, 1 endpoint, 1 endpoint secret, 11 events, 11 delivery jobs, 28 delivery
attempts, migration version `0020`, all FKs resolved, status distribution
matching (1 `dead_letter`, 3 `failed`, 7 `success`).

## 7. Application recovery (restore drill, not production cutover)

Point a **non-production** instance of the app at the restored database and
confirm real queries work -- do not point the actual production deployment
at a restore target as a way to "test" it.

Phase 2 ran the actual service-layer functions the API uses (not toy
queries) against the restored data:
- `app.modules.delivery.query_service.get_delivery_job` -- real
  delivery-detail lookup, correctly returned the job with its attempts
  loaded in chronological order.
- `app.modules.dlq.service.list_dead_letter_jobs` -- correctly found the
  one dead-lettered job.
- A cross-tenant lookup (a random, non-existent organization id) was
  correctly denied (404), confirming tenant isolation survives a restore
  intact.

This is real, but note it exercised the app's query layer directly, not a
running FastAPI process handling real HTTP requests end-to-end against the
restored DB -- that's a reasonable further step if you have a spare
environment to point at it.

## 8. Point-in-time recovery (PITR)

**PITR: NOT AVAILABLE on the current plan.** Render's free Postgres tier
does not offer WAL-based PITR at all -- this is a plan limitation, not
something to configure. No PITR exercise was performed or could be
performed in this environment. If you need PITR, the only path is upgrading
`relayhub-db-user` to a paid Render Postgres plan that includes it (**REQUIRES
MANUAL ACTION / billing decision** -- not made in this phase without your
explicit confirmation).

## 9. RPO (Recovery Point Objective)

**Honest RPO, based on what actually exists:**
- Before this phase: **no backup existed at all** -- RPO was effectively
  "everything since the database was created," i.e. unbounded.
- After this phase, once `BACKUP_DATABASE_URL` is configured: **up to 24
  hours** (the scheduled backup workflow's daily cadence). This is a
  target derived directly from the backup frequency actually implemented,
  not an aspiration.
- If you need a tighter RPO (minutes, not hours), that requires either a
  paid Render plan with PITR, or increasing the GitHub Actions schedule
  frequency (cheap to do, but does not close the gap to true continuous
  WAL-based recovery -- a scheduled dump is still a point-in-time snapshot,
  not continuous).
- **NOT YET ESTABLISHED as a measured, tested number** -- this is a target
  based on schedule frequency, not something proven by an actual
  disaster-to-recovery timing exercise against production.

## 10. RTO (Recovery Time Objective)

**Observed restore time (this phase's drill, local environment):**
- Fresh schema via `alembic upgrade head`: a few seconds (0001 through 0020
  on an empty database).
- Data load (all ~70 rows, via the SQLAlchemy-model-based loader used in
  this drill): well under a minute.
- Integrity + application-level verification queries: a few seconds.
- **Total observed, local, small-dataset restore: well under 5 minutes.**

**This is NOT a production RTO.** It doesn't include: detecting the
incident, obtaining/downloading a real backup artifact, provisioning a new
Render Postgres instance, running a real `pg_restore` against it (untested
in this environment -- see section 5), updating `DATABASE_URL` on the
Render web service, and redeploying. Each of those adds real time this
drill didn't measure. **Target RTO: NOT YET ESTABLISHED** for a full,
production-realistic recovery -- only the data-restore-and-verify portion
has been measured, and only against a small dataset in a local, non-Render
environment.

## 11. Recovery dependencies

To perform a real recovery you need:
- A recent backup artifact (GitHub Actions artifact, once the workflow is
  configured, or a manual `pg_dump` output).
- Render account access (to create/configure the Postgres instance and
  update the web service's `DATABASE_URL`).
- The application's `ENCRYPTION_MASTER_KEY` (required to decrypt
  `endpoint_secrets.encrypted_secret` after restore -- without it, webhook
  signing secrets are unreadable ciphertext. This phase's drill did **not**
  have the real production key and could not verify decryption --
  correctly so; a restore drill should never require production secrets to
  verify structural integrity, but a **real** recovery needs the real key).
- `psql`/`pg_restore` (postgresql-client) on whatever machine performs the
  restore.

## 12. Traffic restoration

Update the Render web service's `DATABASE_URL` environment variable to
point at the restored/new instance, then trigger a redeploy. **Do this only
after section 6-7's verification passes** -- never point production traffic
at an unverified restore.

## 13. Post-recovery checks

- `GET /health/ready` returns 200.
- Celery beat's `check_due_retries`/`reconcile_stuck_jobs` resume logging
  normally (check Render logs).
- Spot-check a few real organizations/endpoints/recent deliveries against
  what you expect from before the incident.
- Watch `delivery_attempts`/`delivery_jobs` for a few minutes to confirm
  new deliveries are processing normally, not erroring.

## 14. Incident documentation

Record: what triggered the incident, when detected, which backup was used
(artifact run ID / timestamp), restore start/end times, verification
results, and any data-loss window (compare backup timestamp to incident
time -- that gap is your actual RPO for this specific incident, which may
differ from the target in section 9).

## 15. Rollback / abort conditions

- If restored data fails integrity checks (section 6), **do not** point
  traffic at it. Try an earlier backup, or escalate -- a partially-correct
  database is worse than a documented outage.
- If you're not certain a step is safe, stop and get a second opinion
  before running anything destructive (`--clean` on `pg_restore` drops
  existing objects in the *target* -- always double, triple check which
  connection string you're pointing at before running it).

## Related documents

- `docs/RELIABILITY.md` -- delivery/retry/DLQ reliability model (Phase 1),
  and the DLQ-replay/attempt-ordering caveat this phase's restore drill
  incidentally re-confirmed still holds after a restore.
- `scripts/backup_db.sh` / `scripts/restore_db.sh` -- the actual commands
  this runbook wraps.
- `.github/workflows/backup.yml` -- the scheduled backup workflow (Phase 2).
