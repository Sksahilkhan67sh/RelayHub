# Where Do I Make My Change?

Concrete, scenario-based navigation. Every path below is real — verified
against this repository, not invented. If your scenario isn't listed, check
[`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md)'s module map for the closest match.

## "I want to add a REST API endpoint"

1. **Schema** — add/extend a Pydantic class in that module's `schemas.py`.
2. **Route** — add the route in that module's `routes.py`. Keep it thin: parse
   input, call a service function, return its result. No business logic here.
3. **Service** — the actual logic goes in `service.py`. Any query touching
   organization-scoped data uses `db.tenant_query.tenant_select(...)`, not a
   bare `select(...)`.
4. **Migration** (if you added/changed a column) — see "database migration"
   below.
5. **Tests** — add to `backend/tests/integration/test_<module>.py`. Run:
   `cd backend && pytest tests/integration/test_<module>.py -v`.
6. **Frontend** — if the dashboard needs to call it, add the call via
   `apps/web/lib/api-client.ts`'s `api.get/post/patch/delete`, and add the
   response shape to `apps/web/lib/types.ts`.

## "I want to change webhook delivery behavior"

- **Signing** → `backend/app/modules/delivery/signing.py`
- **The actual HTTP call + attempt recording** → `delivery/executor.py`'s
  `execute_delivery_job`
- **SSRF/private-IP protection** → `delivery/connect_time_security.py`
  (connect-time) and `endpoints/security.py` (save-time)
- **Tests** → `backend/tests/integration/test_delivery_executor.py`,
  `test_delivery_attempt_ux.py`

## "I want to change retry behavior"

- **Backoff schedule (how long until the next attempt)** →
  `backend/app/modules/retry/schedule.py`'s `compute_next_retry_delay` — this
  is the one source of truth; don't compute a delay anywhere else.
- **What actually triggers a retry attempt** →
  `retry/scheduler.py`'s `enqueue_due_retries`, called by the
  `check_due_retries` Celery beat task (`app/workers/celery_app.py`'s
  `beat_schedule`, `app/workers/tasks.py`'s implementation)
- **Stuck-job recovery** → `retry/reconciliation.py`
- **Tests** → `backend/tests/integration/test_retry_engine.py`,
  `test_reconciliation.py`. `test_retry_engine.py`'s
  `test_full_retry_loop_scanner_actually_triggers_second_attempt` specifically
  exercises the scanner→queue→executor path end to end — the executor-only
  tests in the same file don't prove the scheduler actually drives a second
  attempt, so keep both kinds if you touch this area.
- **Remember:** none of this fires without a running `celery beat` process —
  see `docs/architecture/README.md`'s "Celery / workers" section for why that
  matters in production specifically, not just in tests.

## "I want to modify the DLQ"

- **Everything** → `backend/app/modules/dlq/` (`service.py` for
  list/get/retry/bulk-retry/discard/export logic, `routes.py`, `schemas.py`)
- A job reaches the DLQ when `retry/schedule.py`'s
  `compute_next_retry_delay` returns `None` (attempt budget exhausted) —
  that transition itself happens in `delivery/executor.py`, not in `dlq/`.
- **Tests** → `backend/tests/integration/test_dlq.py`

## "I want to modify realtime delivery status"

1. **The event contract** → `backend/app/modules/realtime/events.py` (read
   the module docstring — it's the authoritative contract). Every field name
   and status value must match `delivery.models.DeliveryJobStatus` exactly.
2. **The publisher** → same file, `emit_delivery_update` — the only function
   that should ever publish this event; don't publish from elsewhere.
3. **The SSE route** → `realtime/routes.py`
4. **The frontend consumer** → `apps/web/lib/realtime.ts` — its
   `DeliveryRealtimeEvent` type is a hand-kept mirror of the backend contract
   (Python and TypeScript can't share a type). **Changing the contract means
   updating both files in the same change**, plus every page that consumes
   the event (search for `useRealtimeDeliveries` or similar in `apps/web/app/(dashboard)`).
- **Tests** → `backend/tests/integration/test_realtime_stream.py`,
  `test_realtime_lifecycle_emits.py`

## "I want to add an AI provider"

1. **Adapter** → new file `backend/app/modules/ai_gateway/adapters/<provider>.py`,
   implementing the same interface as `adapters/base.py`. Translate the
   gateway's neutral `AIGatewayRequest` into that vendor's API call and
   normalize its response into `AIGatewayResponse`, raising the matching
   `AI*Error` subclass from `contracts.py` on failure (auth vs. rate-limit vs.
   timeout vs. unavailable — the gateway's fallback logic depends on getting
   the right subclass, not just any exception).
2. **Register it** → add a `ProviderInfo` entry to
   `ai_gateway/registry.py`'s `_PROVIDERS` dict, listing only the
   `Capability` values your adapter actually implements — don't claim a
   capability (e.g. `STREAMING`) the adapter doesn't really support.
3. **Wire it into the gateway** → add one entry to `ai_gateway/gateway.py`'s
   `_ADAPTER_CLASSES` dict (e.g. `"cohere": CohereAdapter`) — that's the only
   place adapter classes are resolved by provider name; there's no separate
   registration step beyond this and the registry entry above.
4. **Configuration** → add `AI_<PROVIDER>_API_KEY` / `AI_<PROVIDER>_MODEL` to
   `backend/app/core/config.py` and `.env.example`, following the existing
   `AI_OPENAI_*`/`AI_GEMINI_*`/`AI_XAI_*` pattern.
5. **Tests** → add to `backend/tests/unit/` following the pattern of the
   existing adapter tests (mock the HTTP call, assert request shape and error
   mapping) — the AI gateway's own tests use `ai_gateway/fake.py`'s fake
   adapter, so you don't need real network access to test the gateway logic
   itself, only your new adapter's translation layer.
- **Do NOT put provider-specific logic in `insights/ai/` or
  `insights/copilot/`** — those modules only know the gateway's neutral
  contract, never a vendor's actual API shape.

## "I want to modify Copilot"

- **Conversation/context building** → `backend/app/modules/insights/copilot/context.py`
- **The system prompt** → `insights/copilot/prompt.py`
- **The route + request/response schemas** → `insights/copilot/routes.py`
  (mounted at `/v1/insights/intelligence/copilot`), `insights/copilot/schemas.py`
- **The actual AI call** → goes through `ai_gateway/gateway.py` via
  `insights/copilot/service.py` — don't call a provider SDK directly from here
- **Frontend panel** → search `apps/web/app/(dashboard)/intelligence` for the
  Copilot UI
- **Tests** → `backend/tests/integration/test_copilot_api.py`

## "I want to add a frontend page"

1. **Route** → new directory under the matching route group in
   `apps/web/app/` — `(dashboard)/<feature>/page.tsx` for an authenticated
   page, `(marketing)/<feature>/page.tsx` for a public one.
2. **API client calls** → use `apps/web/lib/api-client.ts`'s `api.get/post/patch/delete`
   — never a raw `fetch()` to the backend (the one legitimate exception is
   `lib/realtime.ts`'s SSE `EventSource`, which can't go through a JSON
   client, and `lib/api-client.ts`'s own token-refresh logic, which needs to
   avoid recursing through `api.*`).
3. **Response types** → add/extend the matching interface in `lib/types.ts`.
4. **Components** → reusable UI pieces go in `apps/web/components/`; a
   component used by exactly one page can live in that page's own file (see
   `CONTRIBUTING.md` on not over-splitting files).
5. **Tests** → there's no component test runner currently wired up; at
   minimum, `npx tsc --noEmit` and `npx next lint` must pass.

## "I want to add an SDK feature"

1. **Confirm the backend contract first** — the SDKs are clients, not a
   place to invent new backend behavior. If the endpoint doesn't exist yet,
   build it in `backend/` first (see "add a REST API endpoint" above).
2. **Implement in each SDK you're updating** — `sdks/node/src/`,
   `sdks/python/relayhub/`, `sdks/go/relayhub/`, `sdks/java/src/main/java/...`
   — matching the method naming/shape already used for similar resources in
   that SDK (each SDK has its own idiomatic style; match neighbors within the
   same SDK, not another language's SDK).
3. **Tests** — each SDK has its own test directory alongside its source; add
   a test there using that SDK's existing mocking pattern for HTTP calls.
4. **CLI** (if relevant) — `cli/src/commands/` for a new `relay` subcommand,
   built on `sdks/node`, not a separate HTTP implementation.

## "I want to change authentication"

- **Login/register/token issuance** → `backend/app/modules/auth/service.py`
- **The RBAC dependency every route uses** → `auth/dependencies.py`'s
  `require_role()` and `get_current_auth` — changing these affects every
  protected route in the app; be certain before touching this file.
- **Password reset** → `auth/password_reset_service.py`
- **GitHub OAuth** → `auth/github_oauth.py` (identity fetch, account
  matching/creation) + `auth/github_oauth_routes.py` (the redirect flow, CSRF
  state cookie)
- **JWT/password/API-key cryptography** → `core/security.py` — don't
  hand-roll this elsewhere
- **Tests** → `backend/tests/integration/test_auth_flow.py`,
  `test_github_oauth.py`, `test_password_reset.py`
- **A real, fixed bug worth knowing about:** every member-management endpoint
  (invite, direct add, role change, remove) must check that granting/removing
  the OWNER role specifically requires the actor to already be an owner, not
  just an admin — see `auth/org_service.py`'s guards and
  `tests/integration/test_member_role_escalation.py` before changing any of
  those four functions.

## "I want to change billing"

- **Plan limits + Stripe integration** → `backend/app/modules/billing/service.py`
- **The dependency other modules use to enforce a plan limit** →
  `billing/dependencies.py`
- **Stripe webhook handling** → `billing/routes.py`'s webhook endpoint —
  called by Stripe's servers only, signature-verified, never called by the
  frontend
- **Tests** → `backend/tests/integration/test_billing.py`

## "I want to add/change a database migration"

1. `cd backend && alembic revision -m "short description"` — creates a new
   file in `alembic/versions/`, numbered after the current head.
2. Write `upgrade()` and `downgrade()` — every migration in this repo has
   both; don't skip `downgrade()`.
3. Test it against real Postgres before committing: `alembic upgrade head`,
   confirm the app still starts and the relevant test suite passes, then
   `alembic downgrade -1` to confirm the rollback doesn't error either.
4. Never edit a migration that's already been merged to `main` — add a new
   one instead, even to fix a mistake in a recent one.

## "How do I debug a failed delivery?"

1. Find the `DeliveryJob` row (by event, by endpoint, or by ID) via
   `GET /v1/logs?endpoint_id=...` or `GET /v1/deliveries/by-event/{event_id}`.
2. Its `attempts` array has one `DeliveryAttemptOut` per try — `http_status`,
   `error_category`, `error_message`, `duration_ms` for each.
3. If `status=retrying`, `next_attempt_at` says when the next attempt is
   scheduled — if that time has passed with no new attempt, check that
   `celery beat` is actually running (see the retry-behavior section above).
4. If `status=dead_letter`, it's in `GET /v1/dlq` and can be replayed via
   `POST /v1/dlq/{id}/retry`.
5. Structured application logs (not delivery-specific) are the FastAPI
   process's stdout — on Render, via the dashboard or the `list_logs`
   Render MCP tool if you're an AI agent with that connector.
