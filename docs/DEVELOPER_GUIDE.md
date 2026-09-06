# RelayHub Developer Guide

A map of the repository for someone who has never seen it before. If you're
looking for *how the architecture actually works* (what's implemented vs.
planned, request flow, data model), read
[`docs/architecture/README.md`](architecture/README.md) first — this guide
complements it by answering **"where do I find/put code for X?"** For
scenario-based "I want to change Y" instructions, see
[`WHERE_TO_MAKE_CHANGES.md`](WHERE_TO_MAKE_CHANGES.md).

## Repository layout

```
RelayHub/
├── backend/         FastAPI API + Celery workers (Python)
├── apps/web/         Next.js dashboard + marketing site (TypeScript)
├── sdks/             Node, Python, Go, Java client libraries
├── cli/              Node-based CLI ("relay"), built on sdks/node
├── infra/docker/     docker-compose files + Dockerfiles (the only infra/ content)
├── docs/              Everything you're reading right now
├── examples/         Runnable example scripts (publish an event, verify a signature)
├── scripts/          backup_db.sh / restore_db.sh
└── .github/workflows/   CI, and a few manual ops workflows (SDK publishing, live delivery tests)
```

Every backend module lives at `backend/app/modules/<name>/` and follows the
same internal shape unless noted otherwise:

```
<name>/
├── models.py     SQLAlchemy ORM models for this module's tables
├── schemas.py    Pydantic request/response shapes (the *Out/*Request classes)
├── service.py    Business logic — this is where you put new logic
├── routes.py     FastAPI route handlers — thin, no business logic
└── dependencies.py   (only where the module defines its own FastAPI Depends())
```

Routes call service functions; service functions do the actual work (DB
queries, calling other modules, enqueueing tasks). **A route handler that
contains an `if`/business-rule check, not just a dependency check, is a sign
logic leaked out of `service.py` and should move back.**

## Backend modules

Each entry: purpose, the files you'll actually touch, what it depends on, and
what does *not* belong there.

### `auth/` — authentication, RBAC, organizations, invitations, GitHub OAuth
- **Owns:** login/register/password-reset, JWT issuance + refresh-token
  rotation, the `require_role()` RBAC dependency every other module uses,
  organization/membership CRUD, email invitations, GitHub OAuth login.
- **Key files:** `service.py` (register/login/token issuance),
  `org_service.py` (member management — **any change granting/removing the
  OWNER role must keep the owner-only guard**, see the privilege-escalation
  fix in git history), `invitation_service.py`, `github_oauth.py`,
  `dependencies.py` (`require_role`, `get_current_auth` — the `AuthContext`
  every protected route depends on).
- **Depends on:** `common/notification_client.py` (invite/reset emails),
  `billing/service.py` (creates a subscription for a brand-new org).
- **Don't put here:** anything about *what* a role can do beyond
  authorization — e.g. billing plan limits live in `billing/`, not here.

### `endpoints/` — destination webhook endpoints
- **Owns:** CRUD for the URLs events get delivered to, per-endpoint secret
  (HMAC signing key), SSRF protection (`security.py` — blocks private IPs and
  non-HTTPS URLs outside dev, per `ALLOW_HTTP_ENDPOINTS_IN_DEV`/`ENV`).
- **Don't put here:** delivery execution itself — that's `delivery/`.

### `events/` — event ingestion (the public-facing publish API)
- **Owns:** `POST /v1/events` — validates the API key, creates an `Event` row,
  fans out one `DeliveryJob` per active endpoint subscribed to that event
  type, dispatches each to Celery.
- **Key file:** `service.py`'s `publish_event` — this is the ingestion entry
  point; see `WHERE_TO_MAKE_CHANGES.md` for the full request path.
- **Don't put here:** delivery/signing/retry logic — this module's job ends
  the moment jobs are enqueued.

### `delivery/` — the actual HTTP delivery + signing
- **Owns:** `executor.py`'s `execute_delivery_job` (claims a job, signs the
  payload, makes the HTTP call, records a `DeliveryAttempt`, decides
  retry-vs-terminal), `signing.py` (HMAC-SHA256), `connect_time_security.py`
  (re-checks the destination isn't a private IP *at connect time*, not just
  when the endpoint was saved — defends against DNS rebinding).
- **Depends on:** `retry/schedule.py` for the backoff delay, `realtime/`'s
  `emit_delivery_update` after every state transition.
- **Don't put here:** retry *scheduling* (when to retry) — that's `retry/`.
  This module only executes one attempt and reports the outcome.

### `retry/` — retry scheduling (not execution)
- **Owns:** `schedule.py`'s `compute_next_retry_delay` (the backoff curve —
  the one source of truth for "how long until the next attempt"),
  `scheduler.py`'s `enqueue_due_retries` (what Celery beat's
  `check_due_retries` task actually calls — finds jobs whose
  `next_attempt_at` has passed and re-enqueues them),
  `reconciliation.py` (recovers jobs stuck in `processing` from a crashed
  worker).
- **Critical dependency:** this only works end-to-end if a `celery beat`
  process is actually running — see the "Celery / workers" section of
  `docs/architecture/README.md` for a real incident where it wasn't.
- **Don't put here:** the HTTP call itself — that's `delivery/executor.py`.

### `dlq/` — dead-letter queue
- **Owns:** listing/retrying/discarding/exporting jobs that exhausted their
  retry budget. `service.py`'s `retry_dead_letter_job` re-queues the job's
  *original* signed payload as a fresh attempt — there's no separate
  "replay" module or endpoint.

### `realtime/` — live delivery status via SSE
- **Owns:** `events.py`'s `emit_delivery_update` — the **one** function every
  delivery state-transition call site uses to publish a status update.
  `routes.py` serves the actual SSE stream (`GET /v1/realtime/deliveries/stream`).
- **The event contract is documented in the file itself** (`events.py`'s
  module docstring) — read it before changing any field. The frontend's
  `apps/web/lib/realtime.ts` mirrors it exactly by comment convention, not by
  shared types (Python and TypeScript can't share a type definition) — if you
  change the contract, you must update both, in the same change.
- **Design rule already enforced in code:** a realtime publish failure is
  logged and swallowed, never raised — "realtime is observability/UX
  infrastructure, not delivery infrastructure." Don't change that.

### `insights/` — analytics AI (RCA) + Copilot chat + endpoint health/anomaly detection
- **`insights/aggregation.py`, `incident_engine.py`, `failure_classification.py`**
  — the deterministic (non-AI) health-scoring and incident-detection pipeline;
  runs on a Celery beat schedule (`app/workers/insight_tasks.py`).
- **`insights/ai/`** — AI-assisted root-cause-analysis for a detected
  incident. Calls the AI Gateway (below) through `provider.py`; never talks
  to a provider SDK directly.
- **`insights/copilot/`** — the dashboard's chat feature. Same rule: goes
  through the AI Gateway, never a provider SDK directly.
- **Don't put here:** anything provider-specific (API key handling, request
  formatting for a specific vendor) — that's `ai_gateway/`'s job exclusively.

### `ai_gateway/` — the one place that talks to an AI provider
- **Owns:** a provider-neutral request/response contract (`contracts.py`), a
  registry of which providers have an adapter and what they support
  (`registry.py`), and `gateway.py` — resolve provider → model → validate
  capability → call adapter → normalize response → optional fallback to a
  second provider on transient failure.
- **`adapters/{openai,anthropic,gemini,xai}.py`** — one file per provider,
  each translating the gateway's neutral request into that vendor's actual
  API call. See `WHERE_TO_MAKE_CHANGES.md` for "add a new AI provider."
- **Don't put here:** anything about *why* a call is being made (prompts,
  incident/copilot context) — that's the caller's job (`insights/ai/`,
  `insights/copilot/`).

### `logs/` — delivery log search/export + retention cleanup
- **Owns:** `GET /v1/logs` (search/filter past delivery attempts),
  `/export` (CSV), and `retention.py`'s `cleanup_expired_delivery_logs` —
  the Celery beat task that purges logs past each org's plan-defined
  retention window.

### `analytics/` — dashboard charts/aggregates
- **Owns:** summary/time-series/top-endpoints/export queries backing the
  Analytics and Dashboard pages. Mounted at both `/v1/analytics/*`
  (canonical) and `/v1/insights/*` (a hidden, schema-excluded legacy alias —
  **use the canonical path in any new code**; the alias exists only for
  compatibility, not because it's the "real" name.

### `billing/` — Stripe-backed plans/subscriptions
- **Owns:** plan limits (deliveries/endpoints/retention/rate limits) per
  organization, Stripe Checkout/portal redirects, webhook handling
  (`POST /v1/billing/webhook` — called by Stripe's servers, never by the
  frontend).
- **`dependencies.py`** has the plan-limit-enforcement dependency other
  modules use (e.g. blocking event publishing once the monthly delivery
  limit is hit) — **plan-limit logic belongs here, not duplicated in the
  module being limited.**

### `alerts/` — notification rules (not to be confused with `notifications/`)
- **Owns:** user-configured rules (endpoint down, DLQ spike, high latency →
  email/Slack/Discord/webhook). `sms` exists as a named channel constant with
  no working send path — a deliberate, documented "architecture hook," not a
  bug.
- **Sends through:** `common/notification_client.py` — this module doesn't
  talk to SMTP/Slack/etc. directly.

### `notifications/` — the in-app notification inbox
- **Owns:** the bell-icon dropdown's backing store (member-joined,
  invitation-accepted, abuse-report events) — unrelated to `alerts/`'s
  external notification rules despite the similar name.

### `audit/` — immutable audit log
- **Owns:** one write path (`audit_service.record(...)`) called by every
  module that performs a sensitive mutation. If you add a new sensitive
  action anywhere, call this — don't build a parallel logging mechanism.

### `admin/` — platform-operator-only endpoints
- **Owns:** cross-organization views (all orgs, feature flags, abuse
  reports, force-cancel/retry any delivery job) gated by the separate
  `is_platform_admin` flag, independent of any organization's RBAC role.

### `api_keys/`, `content/`, `newsletter/` — smaller, self-contained modules
- `api_keys/` — live/test API key issuance, scoping, rotation, revocation.
- `content/` — public marketing content (blog posts, job postings) served
  from the DB rather than hardcoded, so non-engineers can publish without a
  deploy.
- `newsletter/` — marketing site email capture.

## Cross-cutting: `backend/app/db/`, `core/`, `common/`, `workers/`

- **`db/tenant_query.py`** — `tenant_select(Model, organization_id)`. **Every
  query for organization-scoped data should go through this**, not a bare
  `select(Model).where(...)` — it's the structural control against
  cross-tenant data leaks, not a per-route convention to remember.
  `db/tenant_isolation_check.py` exists specifically to catch violations.
- **`core/config.py`** — the single `Settings` object (pydantic-settings).
  Every environment variable the app reads is a field here — see
  `docs/CONFIGURATION.md` for the full reference.
- **`core/security.py`** — password hashing, JWT encode/decode, API key
  generation/hashing. **Cryptographic primitives live only here** — don't
  hand-roll hashing/token generation elsewhere.
- **`core/encryption.py`** — Fernet envelope encryption for endpoint signing
  secrets at rest.
- **`core/metrics.py`** — Prometheus `Counter`/`Gauge` definitions, served at
  `GET /metrics`.
- **`core/tracing.py`** — OpenTelemetry setup (real, inactive until
  `OTEL_EXPORTER_OTLP_ENDPOINT` is set).
- **`common/notification_client.py`** — the one place email (Resend HTTP
  API)/Slack/Discord/webhook notifications actually get sent. Both `alerts/`
  and `auth/`'s invitation/password-reset emails go through this — a
  delivery failure here is caught and logged by the caller, never allowed to
  turn an already-committed DB change into a failed request (see git history
  for why this matters — a real bug this exact pattern fixed).
- **`common/queue_client.py`** — `RedisQueueClient`/`InMemoryQueueClient`;
  the abstraction between "enqueue this job" and Celery's actual broker.
- **`workers/celery_app.py`** — the Celery app + beat schedule (the
  authoritative list of what runs on a timer and how often).
- **`workers/tasks.py`** — delivery/retry/cleanup task definitions.
- **`workers/insight_tasks.py`** — the AI/analytics background tasks (run on
  the separate `insights` queue so a slow AI call never delays a webhook
  retry).

## Frontend (`apps/web/`)

```
app/
├── (marketing)/   Public site — statically generated where possible
├── (auth)/        Login, register, password reset, invitation accept, OAuth callback
└── (dashboard)/   The authenticated app -- one directory per feature area,
                   named to match the backend module it talks to
                   (endpoints/, events/, deliveries/, dlq/, analytics/, ...)
lib/
├── api-client.ts       The one HTTP client (api.get/post/patch/delete) --
                        every backend call goes through this
├── auth-context.tsx     React context for the logged-in user + tokens
├── realtime.ts          SSE client for live delivery status
├── types.ts             Hand-maintained TypeScript mirror of backend Pydantic schemas
└── *-data.ts             Static content for docs/marketing pages (not API data)
```

State management: React context only (`auth-context.tsx`, `theme-context.tsx`)
— no Redux/Zustand/etc. Don't introduce one for a single feature; if you
genuinely need shared state beyond a page's own `useState`, that's a
conversation to have first (see `CONTRIBUTING.md`), not a default reach.

`lib/types.ts` is **hand-maintained, not code-generated** from the backend —
if you change a Pydantic schema's shape, update this file in the same PR or
the frontend will silently drift from what the API actually returns.

## SDKs (`sdks/`) and CLI (`cli/`)

Four SDKs (`node`, `python`, `go`, `java`), all covering the same resource
set: auth, API keys, organizations + invitations, endpoints, events,
deliveries, DLQ, analytics, billing, notifications (mapped to the real
`/v1/alerts/*` endpoints — there's no "Projects" resource in the backend, and
no SDK should invent one). `cli/` is a Node CLI built directly on
`sdks/node` — it doesn't re-implement HTTP calls.

## Tests

- **Backend:** `backend/tests/{unit,integration}/`, one file per module,
  named `test_<module>.py` or `test_<feature>.py`. Run against an in-memory
  SQLite DB by default (`backend/tests/conftest.py`) — no local
  Postgres/Redis needed for `pytest`. CI additionally runs the full suite
  against real Postgres+Redis service containers (the `backend-postgres` job)
  to catch anything SQLite's laxer type/constraint checking would miss.
- **Frontend:** `tsc --noEmit` + `next lint` in CI; no component test runner
  is currently wired up (see `CONTRIBUTING.md` before adding one).
- **SDKs/CLI:** each has its own test runner (pytest, `node --test`, `go
  test`, JUnit via Maven) — see each directory's own README/package config.

See `WHERE_TO_MAKE_CHANGES.md` for "what test do I run if I change X."
