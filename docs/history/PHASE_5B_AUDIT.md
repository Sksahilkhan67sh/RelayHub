# RelayHub — Phase 5B Audit

## Phase 5B Scope Source

There is no "Phase 5B" in this repository's own history. The real, documented
history is Phase A → B → C → D → E, and Phase E's closing line is explicit:
*"This is the final production-readiness pass. No Phase F was started."*
"Phase 5B" is a naming convention from outside this repo (it doesn't appear in
`README.md`, any `PHASE_*_REPORT.md`, or `REMAINING_WORK.md`).

Per this project's own stated rule (don't invent a phase when the scope is
ambiguous), the user was asked directly rather than a scope being assumed. They
chose: **build the AI Copilot** — one of the genuinely open items in
`REMAINING_WORK.md` / `PHASE_E_REPORT.md` §14.

## Historical Phase Mapping

- `PHASE_2_REPORT.md`, `PHASE4_VERIFICATION_REPORT.md` — an earlier, separate
  numbering convention (Phase 2 = reliability hardening, Phase 4 = a forensic
  remediation pass) that predates the Phase A–E convention.
- `PHASE_A_REPORT.md` … `PHASE_E_REPORT.md` — the current, final convention:
  A = auth gaps, B = UI gaps, C = marketing/onboarding, D = SDKs/CLI/docs,
  E = production hardening/deployment readiness (final).
- This work is additive on top of Phase E; no prior phase's functionality was
  touched.

## Existing Functionality (relevant to this scope)

`REMAINING_WORK.md` claimed *"AI Copilot / AI layer — no such module exists in
`backend/app/modules`"*. **That claim was stale relative to the actual code.**
On inspection, `backend/app/modules/insights/ai/` already contains a complete
Phase 3 AI system: provider abstraction (Anthropic/OpenAI via `AI_PROVIDER_*`
settings), a prompt builder with real prompt-injection defenses, strict
Pydantic output-schema validation, and an orchestrator that automatically runs
root-cause analysis on incidents — isolated from the delivery path, fails safe,
instrumented with Prometheus metrics. A full REST API
(`/v1/insights/intelligence/...`) exposes it, and — also contrary to
`REMAINING_WORK.md` — the frontend `app/(dashboard)/intelligence/` pages
**already consume that API** and are linked in the dashboard sidebar nav.

## Missing Functionality (what this phase actually built)

1. **A conversational copilot.** What existed was passive, automatic
   per-incident analysis — not something a user could ask a question to.
2. **A chat UI.** No component anywhere called an interactive AI endpoint.

## Broken Functionality

None found in the AI/insights surface. (Stale documentation is not the same as
broken code — see above.)

## Partial Functionality

N/A for this scope.

## Security Findings

- The existing prompt-injection defenses (`insights/ai/prompt.py`) were reused
  verbatim in the new `insights/copilot/prompt.py`, not reinvented.
- New: the copilot's own untrusted-data boundary — the org's account context
  (assembled by `context.py`) is fenced in `<account_context>` tags with an
  explicit "this is data, not instructions" system-prompt directive.
- New: citation grounding — the model's `citations` field is never trusted at
  face value; only incident IDs that were actually present in the assembled
  context survive into the response. Verified by test
  (`test_copilot_chat_success_grounds_answer_and_filters_hallucinated_citations`).
- New: per-organization rate limiting (20 chat messages/hour) — tighter than
  read endpoints, since each call is a paid AI provider request.
- Tenant isolation: `context.py` has no query of its own — every read goes
  through `query_service.py`'s already tenant-scoped functions, so it cannot
  leak cross-tenant data by construction.

## Backend Findings

New module `backend/app/modules/insights/copilot/` (context, prompt, schemas,
service, routes) — see "New Files" below. Mounted at
`POST /v1/insights/intelligence/copilot/chat`. Nothing in `delivery/` or
`dlq/` imports it (same independence guarantee as the existing `ai/` module).

## Frontend Findings

New `components/intelligence/copilot-panel.tsx`, wired into both
`app/(dashboard)/intelligence/page.tsx` (org-wide) and
`app/(dashboard)/intelligence/[incidentId]/page.tsx` (incident-scoped, passes
`incidentId` as focus context). Reuses the existing design system (`Card`,
`Badge`, `Button`, graphite/signal-amber tokens) and `api-client.ts` — no new
HTTP client code.

Also fixed: the marketing Features page's "AI Copilot" entry was marked
"Coming soon" and described capabilities that were never actually planned to
ship this pass (drafting alert rules, suggesting retry policies). Corrected to
describe what's actually shipped (grounded Q&A with citations) and removed the
stale badge.

## Database Findings

**No migration.** The copilot is deliberately stateless server-side — the
client resends conversation history with each request (same pattern documented
in this codebase's own AI-integration precedent). No new tables, no schema
change, per the instruction to avoid unnecessary migrations.

## API Findings

One new endpoint, `POST /v1/insights/intelligence/copilot/chat`, added under
the existing `/insights/intelligence` prefix rather than a new top-level area.
Request/response contracts documented in `copilot/schemas.py`.

## AI Findings

Reuses the existing `AIProvider` protocol, `get_ai_provider()`, and
`AICompletionRequest` unchanged — zero new AI vendor integration code. The
copilot has its own prompt (chat-shaped, not RCA-shaped) and its own output
schema (`CopilotAnswer`, not `AIAnalysisResult`), because the two are
genuinely different: one is a passive per-incident narrative, one is an
interactive Q&A turn — but both are validated with the same
never-trust-raw-text discipline.

## Celery/Redis Findings

Not touched. The copilot is a synchronous read-plus-AI-call request/response
endpoint (same shape as the existing incident-analysis background job's
provider call, just invoked from an HTTP handler instead of a Celery task) —
no new queue, no new worker.

## SDK Findings

Not touched — out of scope for this pass; Java SDK Maven verification remains
the one open SDK item, unchanged from Phase D's status.

## CLI Findings

Not touched — no CLI command exists for chat-style interaction, and none was
requested.

## Test Gaps

| Feature | Existing Tests | New Tests |
|---|---|---|
| Copilot schema validation | — | 4 unit tests |
| Copilot prompt sanitization | — | 3 unit tests |
| Copilot chat route (auth, rate limit, disabled/enabled, citation filtering, malformed-output fail-safe, oversized input) | — | 6 integration tests |

No frontend test harness exists in this repo (confirmed — no Jest/Playwright
config found), so the new UI component was verified via `tsc --noEmit` and
`next lint` only, consistent with how every other frontend change in this
repo's history has been verified.

## P0 / P1 / P2 / P3

- P0: none outstanding for this scope.
- P1: `REMAINING_WORK.md` is now measurably stale (see Findings above) — this
  report supersedes it for the AI/insights section; the file itself wasn't
  rewritten wholesale to avoid unrelated churn, but should be updated in a
  follow-up pass.
- P2: Java SDK Maven verification (pre-existing, environment-blocked, unrelated
  to this phase).
- P3: none new.

## Exact Phase 5B Scope

Ship a conversational AI copilot (backend chat endpoint + frontend chat UI)
grounded in the organization's own incident/health data, reusing the existing
AI provider abstraction and RBAC/tenant-isolation machinery — without
duplicating the existing passive RCA system or building a second AI
architecture.

## Implementation Order

5B.1 Backend (context → prompt → schemas → service → routes) → 5B.9 Tests
(unit + integration) → 5B.6 Frontend (types → component → wire into both
pages → marketing copy fix) → 5B.10 Runtime verification (pytest, ruff, mypy,
tsc, next lint, next build attempt).
