# RelayHub Architecture

This document describes the architecture as it actually exists in this
repository. Every claim below is traceable to a specific file. Where something
is planned but not built, it is labeled **Planned / Not currently implemented**
rather than described as working.

## System overview

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
              async     │          │  enqueue delivery/retry jobs
              queries    ▼          ▼
                 ┌──────────┐  ┌──────────────┐
                 │PostgreSQL│  │ Redis (queue, │
                 │          │  │ cache, Celery │
                 └──────────┘  │ broker/result)│
                                └──────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │ Celery workers  │  backend/app/workers
                              │ + Celery beat   │  (deliver_webhook,
                              └────────────────┘   check_due_retries,
                                                    cleanup_expired_logs)
```

**IMPLEMENTED:** frontend, backend API, PostgreSQL, Redis, Celery workers + beat,
the full auth/RBAC/multi-tenancy/delivery/retry/DLQ/billing/alerts/audit stack
described below, and an AI Gateway (Copilot chat + incident root-cause
analysis) — see the "AI layer" section further down for its actual shape.

**NOT IMPLEMENTED:** Kafka (no message broker other than Redis exists anywhere
in this codebase), Kubernetes manifests, Nginx config, or Grafana dashboards
(`infra/` currently contains only `infra/docker/` — no `k8s`, `nginx`, or
`grafana` directories exist to check).

## Frontend

`apps/web` -- Next.js 14, App Router, TypeScript, Tailwind. Three route groups:

- `(marketing)` -- the public site (landing, pricing, docs, blog, etc). Statically generated.
- `(auth)` -- login, register, password reset, invitation accept flows.
- `(dashboard)` -- the authenticated application, gated by a client-side redirect
  in `app/(dashboard)/layout.tsx` that checks `useAuth()`.

State: React context for auth (`lib/auth-context.tsx`) and theme
(`lib/theme-context.tsx`), no global state library. API access goes through a
single typed client (`lib/api-client.ts`) that attaches the bearer token from
localStorage and normalizes error responses.

**IMPLEMENTED.** See `docs/history/PHASE_A_REPORT.md` / `docs/history/PHASE_B_REPORT.md` / `docs/history/PHASE_C_REPORT.md` for the build history.

## Backend

`backend/app` -- FastAPI, async throughout (`asyncpg` via SQLAlchemy's async
engine), organized as one module per resource under `app/modules/` (`auth`,
`api_keys`, `endpoints`, `events`, `delivery`, `logs`, `dlq`, `analytics`,
`billing`, `alerts`, `audit`, `admin`). Each module follows the same
routes → service → models layering; routes never touch the database directly.

Health check: `GET /health/live` (see `Dockerfile`'s `HEALTHCHECK` directive).

**IMPLEMENTED.**

## PostgreSQL

Primary datastore, accessed via SQLAlchemy's async ORM. Schema managed by
Alembic migrations (`backend/alembic/versions/`, 12 migrations as of this
phase). Every table that holds organization-scoped data carries an
`organization_id` column.

**IMPLEMENTED.**

## Redis

Three logical uses, all against the same Redis instance by default (different
DB indices):

1. **Delivery/retry dispatch** -- `backend/app/common/queue_client.py`
   (`RedisQueueClient`) hands each job straight to Celery's own broker
   (`celery_app.send_task("deliver_webhook", ...)`), with an `InMemoryQueueClient`
   used in tests. **Phase E fix:** this used to `RPUSH` onto a separate,
   never-consumed Redis list (`relayhub:delivery_queue`) -- nothing in the
   codebase ever popped it, so every published event created a `DeliveryJob`
   row that no worker would pick up. Confirmed live during Phase E's
   end-to-end smoke test and fixed by dispatching through Celery's broker
   directly, so there's one real queue instead of two (one real, one dead).
2. **Rate limiting** -- `backend/app/common/rate_limiter.py`, a sliding-window-log
   implementation backed by Redis sorted sets.
3. **Celery broker + result backend** -- `CELERY_BROKER_URL` (Redis DB 1),
   `CELERY_RESULT_BACKEND` (Redis DB 2), configured in `backend/app/workers/celery_app.py`.

**IMPLEMENTED. No Kafka or other message broker exists anywhere in this codebase.**

## Celery / workers

`backend/app/workers/celery_app.py` defines the Celery app and its beat
schedule; `backend/app/workers/tasks.py` defines the tasks:

- `deliver_webhook` -- executes a single delivery attempt for one job.
- `check_due_retries` -- runs every 10 seconds (via Celery beat) and enqueues
  any delivery whose scheduled retry time has passed.
- `cleanup_expired_delivery_logs` -- runs once a day, purges delivery logs past
  the organization's plan-defined retention window.

`docker-compose.yml` and `docker-compose.prod.yml` run Celery as three
separate services: `worker` (default queue: delivery/retry tasks),
`worker-insights` (the `insights` queue: AI/analytics background tasks, kept
separate so a slow AI provider call can never delay a webhook retry), and
`beat` (the scheduler) -- this split is real, not aspirational.

**Operational lesson worth knowing:** the actual production deployment
(Render) doesn't use this docker-compose topology -- it runs a single
container (`backend/start.sh`) that bundles worker + API together for cost
reasons. That script omitted `beat` entirely for a period, so retries only
ever fired once — `check_due_retries` never ran outside a properly
configured `beat` process, so a job stuck at `retrying` had nothing to move
it forward. Fixed by adding `beat` as a third background process in
`start.sh` too. The lesson: if you ever change how this app is deployed
outside `docker-compose.yml`, `beat` running is not optional.

**IMPLEMENTED.**

## Authentication

Two schemes (see [`docs/api/README.md`](../api/README.md#authentication) for
the full breakdown): short-lived session bearer tokens with refresh-token
rotation for the dashboard, and independently-revocable, scoped API keys for
event publishing. Passwords and API keys are hashed before storage; endpoint
signing secrets are encrypted at rest via Fernet/AES envelope encryption
(`ENCRYPTION_MASTER_KEY`).

**IMPLEMENTED.**

## RBAC

Four roles (`owner`, `admin`, `member`, `viewer`), enforced server-side on every
route via FastAPI dependencies (`require_role(...)` in
`backend/app/modules/auth/dependencies.py`) -- not just hidden in the frontend.
A separate, orthogonal `is_platform_admin` flag gates the entire `/admin/*`
module regardless of organization role.

**IMPLEMENTED.**

## Multi-tenancy

Every organization-scoped table carries `organization_id`, and the data-access
layer scopes queries by it rather than leaving that to individual route
handlers to remember (see `db/tenant_query.py`). There is no code path that
crosses tenants by omission.

**IMPLEMENTED.**

## Webhook delivery pipeline

`POST /events` (API-key authenticated) creates an `Event` row and one
`DeliveryJob` per subscribed, active endpoint, then dispatches each job to
Celery. A worker process picks up `deliver_webhook`, signs the
payload (HMAC-SHA256, per-endpoint secret), sends the HTTP POST, and records a
`DeliveryAttempt` with status/latency/response.

**IMPLEMENTED.**

## Retry pipeline

A failed attempt (non-2xx or timeout) schedules `next_attempt_at` on the job
using exponential backoff, capped by the endpoint's `max_retry_attempts`.
`check_due_retries` (Celery beat, every 10s) finds jobs whose `next_attempt_at`
has passed and re-enqueues them. Once the attempt cap is hit, the job's status
becomes `dead_letter`.

**IMPLEMENTED.**

## Replay

Not a separate pipeline -- replay is `POST /dlq/{id}/retry` (or `/bulk-retry`):
it re-enqueues a dead-lettered job's original signed payload as a new attempt.

**IMPLEMENTED** (as a DLQ operation, not a standalone `/replay` endpoint -- see
`docs/api/dlq.md`).

## DLQ

`backend/app/modules/dlq` -- jobs whose retry budget is exhausted move to a
queryable, filterable dead-letter state rather than being deleted. Supports
list/get/retry/bulk-retry/discard/CSV export.

**IMPLEMENTED.**

## Billing

Stripe-backed (`backend/app/modules/billing`). Plans (Free/Starter/Pro/Enterprise)
carry delivery/endpoint limits, retention, rate limits, and feature flags.
`POST /billing/checkout` and `/portal` redirect through Stripe-hosted pages.
Exceeding the plan's monthly delivery limit blocks further deliveries rather
than silently over-billing.

**IMPLEMENTED.**

## Notifications / alerts

`backend/app/modules/alerts` -- rule-based: a condition type (endpoint down, DLQ
spike, high latency, etc), a severity, a channel (email/Slack/Discord/webhook),
and a threshold config. `sms` exists as a named channel constant with a comment
marking it an "architecture hook" but has no working send implementation.

**IMPLEMENTED** (email/Slack/Discord/webhook). **SMS: Planned / Not currently implemented.**

## Audit logging

`backend/app/modules/audit` -- every sensitive account action writes an
immutable row with actor, action, resource, IP, and timestamp.

**IMPLEMENTED.**

## Observability

Structured logging exists throughout the request path.

**Metrics: real, not a placeholder.** `GET /metrics` (`backend/app/main.py`)
serves a standard Prometheus-format scrape combining two sources (see
`backend/app/core/metrics.py`'s module docstring for why they're split):
`prometheus_fastapi_instrumentator`'s automatic HTTP request metrics, plus
hand-defined `Counter`/`Gauge` metrics for things that only make sense
refreshed from a live DB query at scrape time (queue depth, worker health)
rather than accumulated in-process — necessary because Celery workers are
separate processes from the API process that serves `/metrics`.

**Distributed tracing: real code, off by default.** `backend/app/core/tracing.py`'s
`setup_tracing()` wires an actual `OTLPSpanExporter` and registers
`FastAPIInstrumentor` when `OTEL_EXPORTER_OTLP_ENDPOINT` is set — this is a
genuine OpenTelemetry integration, not an unused config placeholder. With the
setting unset (the default everywhere so far), `setup_tracing()` returns
`None` and the app skips instrumentation entirely — zero overhead, not a
half-implemented feature silently failing.

There are no Grafana dashboards — `infra/` has no `grafana` directory to
check (see the System overview section above).

**IMPLEMENTED: Prometheus metrics, structured logging, and OpenTelemetry
tracing (inactive until `OTEL_EXPORTER_OTLP_ENDPOINT` is configured).
Grafana dashboards: Planned / Not currently implemented.**

## AI layer

Real, implemented, and live in production (this section was previously stale —
see `docs/development-history.md` for when it was actually built). Three
distinct pieces, each with one job:

```
Insights AI (RCA)  ──┐
                      ├──▶  AI Gateway  ──▶  Provider Adapter  ──▶  External API
Copilot (chat)     ──┘      (contracts,      (openai/anthropic/
                             registry,         gemini/xai)
                             fallback,
                             metrics)
```

- **`backend/app/modules/ai_gateway/`** — the single place that knows how to
  talk to an AI provider. `contracts.py` defines a provider-neutral
  request/response/error shape; `registry.py` tracks which providers have an
  adapter and what each supports; `gateway.py` resolves provider → model →
  validates the request needs a capability the provider actually has → calls
  the adapter → normalizes the response → falls back to a second provider on
  a transient failure, if `AI_FALLBACK_PROVIDER` is configured.
  `adapters/{openai,anthropic,gemini,xai}.py` each translate the gateway's
  request shape into that vendor's actual API call. **This module has no
  knowledge of incidents, prompts, or copilot context** — that boundary is
  deliberate (see the module's own docstrings).
- **`backend/app/modules/insights/ai/`** — root-cause-analysis for incidents.
  Builds a prompt from incident/anomaly data (`prompt.py`), calls the gateway
  through a thin `provider.py` shim, validates the response against its own
  JSON schema (`schemas.py`).
- **`backend/app/modules/insights/copilot/`** — the dashboard's Copilot chat.
  Builds conversational context (`context.py`), its own prompt (`prompt.py`),
  routes live at `/v1/insights/intelligence/copilot`.

Disabled by default (`AI_PROVIDER_ENABLED=false`) — with no key configured,
every call fails fast with a clear "AI is not configured" error rather than a
confusing timeout or a fake response. See `docs/CONFIGURATION.md` for every
`AI_*` setting, and `docs/DEVELOPER_GUIDE.md`'s "I want to add an AI
provider" walkthrough for extending this.
