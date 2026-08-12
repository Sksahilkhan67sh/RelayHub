# RelayHub

RelayHub is a multi-tenant webhook and event-delivery platform: publish an
event once via API, and RelayHub signs, delivers, retries, and tracks it to
every subscribed destination endpoint for your organization.

This README describes the product as it actually exists in this repository.
For the full build history and phase-by-phase verification detail, see
[`docs/development-history.md`](docs/development-history.md) and
`PHASE_A_REPORT.md` through `PHASE_E_REPORT.md`. For a claim-by-claim,
file-traceable architecture reference, see
[`docs/architecture/README.md`](docs/architecture/README.md).

## Core capabilities

- **Webhook delivery**: publish an event, RelayHub delivers it (HMAC-signed)
  to every active endpoint subscribed to that event type
- **Retries**: failed deliveries are automatically retried on a schedule
- **Dead-letter queue (DLQ) + replay**: deliveries that exhaust retries land
  in the DLQ and can be manually replayed
- **Multi-tenant organizations**: every resource is scoped to an
  organization; RBAC roles (owner/admin/member/viewer) gate what a member can do
- **API keys**: live/test key environments, scoped permissions, one-time
  secret reveal at creation
- **Team management**: email invitations, member roles, revocation
- **Analytics**: delivery volume, latency percentiles, success/failure rates
- **Alerts**: email/Slack/Discord/webhook notifications on delivery failures
  and other events (SMS is a documented, not-yet-implemented channel — see
  Current limitations)
- **Billing**: plan/subscription management via Stripe (injectable client)
- **Audit log**: every mutating action across the platform is recorded
- **Admin panel**: platform-level organization, feature-flag, and abuse-report
  management for RelayHub operators
- **SDKs** (Node.js, Python, Go, Java) and a **CLI** for programmatic access

## Architecture

```
                    ┌──────────────────┐
  Browser  ───────▶ │  Next.js frontend │  apps/web (App Router)
                    └────────┬─────────┘
                             │ REST (fetch), Bearer token
                             ▼
                    ┌──────────────────┐
  3rd-party  ─────▶ │  FastAPI backend  │  backend/app (async, uvicorn)
  (API key)         └───┬──────────┬───┘
                        │          │
              async     │          │  dispatch delivery/retry jobs
              queries    ▼          ▼
                 ┌──────────┐  ┌──────────────┐
                 │PostgreSQL│  │ Redis (cache, │
                 │          │  │ Celery broker/│
                 └──────────┘  │ result store) │
                                └──────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │ Celery workers  │  backend/app/workers
                              │ + Celery beat   │  (deliver_webhook,
                              └────────────────┘   check_due_retries,
                                                    cleanup_expired_logs)
```

No Kafka, no Kubernetes manifests, no Nginx config, and no AI/copilot service
exist anywhere in this codebase — see `docs/architecture/README.md` for the
full implemented-vs-planned breakdown.

### Backend stack

FastAPI (async), SQLAlchemy 2.0 (async), Alembic migrations, PostgreSQL,
Redis, Celery (worker + beat), Pydantic for request/response schemas.
Structured, module-per-domain layout under `backend/app/modules/`.

### Frontend stack

Next.js 14 (App Router), TypeScript, Tailwind CSS. Three route groups: the
public marketing site (statically generated), auth flows (login, register,
password reset, invitation accept), and the authenticated dashboard.

### PostgreSQL / Redis / Celery

- **PostgreSQL** is the system of record for every resource (organizations,
  users, endpoints, events, deliveries, invitations, audit log, billing state).
  Connection pooling is configured via `DATABASE_POOL_SIZE`/`DATABASE_MAX_OVERFLOW`.
- **Redis** serves three roles: the rate-limiter's sliding-window counters,
  the Celery broker, and the Celery result backend (separate logical DB
  indexes for each, see `backend/.env.example`).
- **Celery** runs the delivery/retry workers and a beat scheduler
  (`check_due_retries`, `cleanup_expired_delivery_logs`).

### Webhook flow: ingestion → queue → worker → destination

1. `POST /v1/events` (API-key authenticated) creates an `Event` row and one
   `DeliveryJob` per subscribed, active endpoint.
2. Each job is dispatched to Celery's broker (`deliver_webhook` task).
3. A worker signs the payload (HMAC-SHA256, per-endpoint secret), sends the
   HTTP POST to the destination, and records a `DeliveryAttempt` (status code,
   headers, latency, error category).
4. The job reaches a terminal state (`delivered`/`failed`) or, if retries
   remain, is rescheduled by the retry pipeline.

### Retry / DLQ / replay

Failed deliveries are retried on a backoff schedule up to a configurable
attempt limit. Once exhausted, a job moves to the DLQ, where it's visible via
`GET /v1/dlq` and can be manually replayed (re-queued as a fresh delivery
attempt) or left as a permanent record.

### Authentication and authorization

- **Dashboard auth**: JWT access tokens (15 min) + rotating refresh tokens
  (30 day, with reuse/family-based revocation detection), bcrypt password
  hashing.
- **API auth**: a separate `X-RelayHub-Api-Key` header scheme for the public
  Event API, distinct from dashboard JWTs, with scoped permissions
  (`events:write`, `events:read`, `deliveries:read`, `endpoints:read/write`, etc.).
- **RBAC**: owner/admin/member/viewer roles, enforced via a shared
  `require_role()` dependency used by every module.
- **Tenant isolation**: organization-scoped queries are centralized in
  `backend/app/db/tenant_query.py` rather than left to individual routes to
  remember — a structural control against cross-tenant access, not a
  per-route convention.

### Multi-tenant organization model

Every resource carries an `organization_id`. Users belong to organizations
via memberships with a role. Invitations (hashed, single-use, expiring
tokens) bring new members in by email.

### API keys

Live and test key environments, scoped permissions, one-time full-secret
reveal at creation (masked everywhere after), rotation (revoke + reissue,
fully audited), and immediate rejection on revocation — no caching window.

### SDK availability

| SDK | Status |
|---|---|
| Node.js / TypeScript | ✅ tested (`sdks/node`) |
| Python | ✅ tested (`sdks/python`) |
| Go | ✅ tested (`sdks/go`) |
| Java | ⚠️ written and reviewed against the live API; compilation/test execution has been environment-limited so far in every sandbox this project has been built in (Maven Central unreachable) — see `PHASE_E_REPORT.md` for the exact, current status |

All four cover the same real resource set (auth, API keys, organizations +
invitations, endpoints, events, deliveries, DLQ, analytics, billing,
notifications) and map "notifications" to the real `/v1/alerts/*` endpoints.
There is no "Projects" resource in the backend, and none of the SDKs invent one.

### CLI

`cli/` — a Node-based CLI (`relay`) built on the Node SDK, with `login`,
`logout`, `whoami`, `endpoints`, `publish`, `deliveries`, `replay`, `dlq`,
`analytics`, `billing`, `notifications`, `config`, `doctor`, `completion`, and
`version` commands. See `docs/cli/README.md` for the full command reference.

### Documentation location

- `docs/architecture/README.md` — implemented-vs-planned architecture reference
- `docs/api/` — API reference, one file per backend module
- `docs/self-hosting/README.md` — deployment/self-hosting guide
- `docs/webhooks/README.md` — signing, verification, retry, idempotency
- `docs/sdks/README.md`, `docs/cli/README.md` — SDK/CLI reference
- `examples/` — runnable examples (event publish, webhook receiver, signature verification)
- `PHASE_A_REPORT.md` … `PHASE_E_REPORT.md` — build/verification history
- `RELEASE_CHECKLIST.md` — the full, current verification checklist

## Local development

```bash
# Backend
cp backend/.env.example backend/.env   # fill in real local values
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cp apps/web/.env.example apps/web/.env.local
cd apps/web
npm install
npm run dev
```

Backend tests use an in-memory SQLite database by default (see
`backend/tests/conftest.py`) — no local Postgres/Redis is required to run the
test suite.

## Environment setup

Every environment variable the backend reads is documented, categorized, in
[`backend/.env.example`](backend/.env.example) (app, auth/secrets, database,
Redis/Celery, CORS, rate limiting, webhook SSRF protection, Stripe, email,
observability). The frontend's one variable is in
[`apps/web/.env.example`](apps/web/.env.example). Never commit a real `.env`
or `.env.local` file — both are excluded via `.gitignore`.

## Docker / production deployment

- `infra/docker/docker-compose.yml` — local development (bind-mounted source,
  `--reload`, ports published to the host)
- `infra/docker/docker-compose.prod.yml` — production topology (no
  bind-mounts, Postgres/Redis not published to the host, multiple `uvicorn`
  workers, restart policies, includes the frontend service)
- `backend/Dockerfile`, `apps/web/Dockerfile` — production images (non-root
  user, healthchecks, standalone Next.js output)

```bash
cp backend/.env.example backend/.env   # fill in real production values
docker compose -f infra/docker/docker-compose.prod.yml up -d --build
```

See `docs/self-hosting/README.md` and `PHASE_E_REPORT.md` §16 for the full
deployment walkthrough and what must be configured outside this repo (DNS,
TLS termination, a reverse proxy — intentionally not included here to avoid
adding infrastructure the existing architecture doesn't call for).

## Health checks

- `GET /health/live` — pure liveness check, no dependency calls
- `GET /health/ready` — checks real Postgres + Redis connectivity, returns
  `503` with per-dependency detail if either is down

## Backup / restore

`scripts/backup_db.sh` (`pg_dump --format=custom`) and
`scripts/restore_db.sh` (`pg_restore --clean --if-exists`), both built around
the same `DATABASE_URL` the application uses. See the scripts' own comments
for usage and the current verification status in `PHASE_E_REPORT.md`.

## CI/CD

`.github/workflows/ci.yml` runs backend (pytest/ruff/mypy against real
Postgres+Redis service containers), frontend (typecheck/lint/build), all four
SDKs, the CLI, and a Docker build-validation job on every push/PR to `main`.

## Testing / verification

See `RELEASE_CHECKLIST.md` for the complete, current test/lint/typecheck
results across every component, and `PHASE_E_REPORT.md` for what was verified
live against real infrastructure versus what remains environment-limited in
the sandbox this project has been built in.

## Security notes

- Passwords hashed with bcrypt; password-reset and invitation tokens are
  stored only as SHA-256 hashes (raw tokens never persisted) and are
  single-use with expiry
- Rate limiting is a real Redis-backed sliding window, shared by the
  login and forgot-password endpoints
- Outbound webhook targets are checked against private-IP ranges by default
  (`BLOCK_PRIVATE_IP_TARGETS`) to reduce SSRF risk
- Baseline security response headers (X-Content-Type-Options, X-Frame-Options,
  Referrer-Policy, Permissions-Policy, HSTS in production) are applied to
  every response
- Request bodies over 2 MiB are rejected before reaching route handlers
- See `PHASE_E_REPORT.md` §2 for the full security audit and the one known,
  still-open item below

## Current limitations

These are real, current gaps — not aspirational "coming soon" items:

- **Frontend token storage uses `localStorage`, not an httpOnly cookie.**
  Documented tradeoff, not yet hardened into a session/cookie-based flow.
- **SMS alert channel** is a named constant with no working send path.
- **OpenTelemetry** (`OTEL_EXPORTER_OTLP_ENDPOINT`) is a configuration
  placeholder only — no tracing instrumentation exists behind it.
- **Kubernetes/Nginx/Grafana** configuration directories under `infra/` are
  empty — not part of the current deployment model, which is Docker Compose.
- **Java SDK** has not been mechanically compiled/tested in any sandbox this
  project has been developed in so far (Maven Central has been unreachable in
  every environment used) — it's written and reviewed against the live API,
  but unverified.
- **No AI/copilot feature** exists in this codebase.

## License / project information

No `LICENSE` file is currently present in this repository. Treat the code as
proprietary/all-rights-reserved unless and until a license file is added.
