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
described below.

**NOT IMPLEMENTED:** Kafka (no message broker other than Redis exists anywhere
in this codebase), Kubernetes manifests (`infra/k8s` is an empty directory),
Nginx config (`infra/nginx` is empty), Grafana dashboards (`infra/grafana` is
empty), an AI/copilot service (no such module exists in `backend/app/modules`).

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

**IMPLEMENTED.** See `PHASE_A_REPORT.md` / `PHASE_B_REPORT.md` / `PHASE_C_REPORT.md` for the build history.

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

`docker-compose.yml` runs two separate Celery containers: `worker` (executes
tasks) and `beat` (schedules them) -- this split is real, not aspirational.

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

Structured logging exists throughout the request path. An
`OTEL_EXPORTER_OTLP_ENDPOINT` setting exists in `backend/app/core/config.py`,
but no OpenTelemetry instrumentation code (spans, tracers, exporters) exists
anywhere else in the codebase -- the setting is a placeholder for future wiring,
not active tracing today. There are no Grafana dashboards (`infra/grafana` is an
empty directory) and no Prometheus/metrics-scraping endpoint.

**Structured logging: IMPLEMENTED. Distributed tracing / metrics dashboards: Planned / Not currently implemented.**

## AI layer

**No AI/copilot service exists anywhere in `backend/app/modules`.** The
"AI Copilot" feature referenced on the marketing Features page is explicitly
labeled "Coming soon" there and has no backend counterpart. **Not implemented.**
