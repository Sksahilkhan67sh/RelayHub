# RelayHub — Remaining Work

Honest list of what's left, in three tiers. Nothing here is hidden or silently stubbed
in the code — every item below is either a documented design boundary or a genuinely
unstarted future phase.

## Tier 1 — needs backend design work before any frontend can be built

- ✅ **DONE (Phase A).** ~~Password reset flow.~~ Implemented:
  `POST /v1/auth/forgot-password` / `POST /v1/auth/reset-password`, with
  one-time expiring tokens, rate limiting, and audit logging. See
  `PHASE_A_REPORT.md` and `docs/api/auth.md`.
- ✅ **DONE (Phase A).** ~~Invite-token / accept-registration email flow.~~
  Implemented: `POST /v1/org/invitations` + accept flow, no existing account
  required. See `PHASE_A_REPORT.md` and `docs/api/organizations.md`.

## Tier 2 — real UI gaps with no missing backend, safe to pick up any time

- ✅ **DONE (Phase B).** ~~Command palette (⌘K).~~ Implemented: fuzzy search,
  keyboard nav, live search across real resources, recents. See `PHASE_B_REPORT.md`.
- ✅ **DONE (Phase B).** ~~Dark/light mode toggle.~~ Implemented: system
  detection, localStorage persistence, no flash on load. See `PHASE_B_REPORT.md`.
- ✅ **DONE (Phase B).** ~~Per-org feature-flag override UI.~~ Implemented,
  including the `GET /admin/feature-flags/{key}/overrides` endpoint added
  specifically to support it. See `PHASE_B_REPORT.md`.
- ✅ **DONE (Phase C).** ~~Public landing/pricing pages, onboarding flow.~~
  Landing, features, pricing, docs home, about, careers, contact, changelog,
  blog, status, legal pages, and 404 are all built. Onboarding flow (a guided
  first-run experience inside the dashboard) was the one item from this
  bullet still open after Phase C — **now done, see the Phase D closeout
  section below.**

## Tier 3 — known, low-risk technical debt (documented, not fixed this pass)

- **10 residual mypy findings**, all in SQLAlchemy/Stripe-SDK typing friction, zero
  runtime impact (confirmed by the full 186/186 test suite):
  - `db/tenant_query.py:25` — dynamic `getattr()`-based soft-delete column lookup;
    mypy can't narrow `Any | None` here without a `cast()`.
  - `common/stripe_client.py` (3 findings) — the untyped `stripe` SDK; would need
    `stripe`'s official type stubs installed as a dev dependency to resolve cleanly.
  - `core/error_handlers.py` (2 findings) — Pydantic v2 validation-error dict shape is
    typed loosely by Pydantic itself here.
  - `modules/analytics/service.py:103` — `InstrumentedAttribute` vs `ColumnElement`
    overload mismatch, a known SQLAlchemy 2.0 typing rough edge with `date_trunc`-style
    helper functions.
  - `modules/billing/service.py` (2 findings) — `getattr()` on a loosely-typed Stripe
    webhook payload object flowing into a `str`-typed helper.

  None of these represent incorrect behavior — the test suite exercises all of these
  code paths and passes. Recommended real fix, when picked up: add `stripe`'s official
  type stubs and a couple of targeted `cast()` calls at the SQLAlchemy dynamic-attribute
  sites, rather than broadening `mypy`'s ignore surface.
- **Token storage (localStorage, not httpOnly cookies).** Documented tradeoff in
  `apps/web/lib/api-client.ts` itself. The real fix is routing auth through Next.js
  Route Handlers as a BFF so the browser never holds the token directly. Non-trivial
  (touches every API call's auth flow) — correctly scoped as its own hardening pass
  rather than folded into this one.
- **No worker/process heartbeat table.** The admin panel's system-health view is
  honest about this already (explicit "not tracked yet" callout in the UI, per the
  README) rather than fabricating a `workers: healthy` field with nothing behind it.
  Needs a real heartbeat mechanism (Celery worker registering into Redis/Postgres
  periodically) before this can show real data.
- **Percentile calculation is O(n) in Python**, not pre-aggregated. Documented and
  intentional in `analytics/percentiles.py` — correct at current scale, flagged in the
  code itself as needing rollups or t-digest/HdrHistogram before much higher attempt
  volume.

## Explicitly not attempted this pass, on purpose

- Did not touch the Stripe SDK typing (would add a new dependency for a
  non-functional benefit).
- Did not attempt a `mypy --strict` pass (the codebase was never type-checked before
  this audit; going straight to `--strict` on a first pass risks a large, low-value
  diff against otherwise-working, tested code).
- Did not build a fake/local-only command palette or password-reset UI just to make
  the page list look complete — both would be placeholder implementations with nothing
  real behind them, which contradicts the task's explicit instructions.

---

## Phase D update — Developer Experience & Ecosystem

Additive; nothing above was deleted. See `PHASE_D_REPORT.md` for the full account.

### Done this phase

- ✅ Node.js and Python SDKs — built, tested, verified (12/12 and 13/13 tests).
- ✅ Go and Java SDKs — written, covering the same resource surface — **but
  unverified** (see Environment limitations below).
- ✅ CLI (`relay`) — 15 commands, built on the Node SDK, typechecked, built, and
  smoke-tested.
- ✅ Full API reference (`docs/api/`), architecture docs (`docs/architecture/`),
  self-hosting guide (`docs/self-hosting/`), webhook developer guide
  (`docs/webhooks/`), SDK docs (`docs/sdks/`), CLI docs (`docs/cli/`).
- ✅ Developer examples, all actually executed and verified during this phase:
  Node/Python event publishing, Node DLQ replay, a real webhook receiver tested
  with both a valid and an invalid signature (200 / 401 respectively), and
  standalone signature verification in both Node and Python with 3 passing
  assertions each.
- ✅ Found and fixed real schema drift between the first Phase D SDK pass and
  the actual `alerts`/`billing`/`analytics` backend schemas — see
  `RELEASE_CHECKLIST.md`'s Phase D section for the specifics. This also caught
  and fixed two consequent CLI bugs (`billing usage`, `notifications`).

### Environment limitations (not code defects)

- **Go SDK: no Go toolchain in this environment.** `go build`/`go test`/`gofmt`
  were never run. The code was written and manually reviewed with extra care,
  but has zero mechanical verification. Run `go build ./... && go test ./...`
  before depending on it.
- **Java SDK: no JDK compiler in this environment** (only a JRE — no `javac`)
  **and Maven Central is unreachable** from this sandbox's network allowlist,
  so not even a dependency-stub compile check was possible. Same disclosure as
  Go: written and reviewed, zero mechanical verification. Run
  `mvn compile test` before depending on it.
- **Frontend `next build`** has the same Google Fonts sandbox restriction
  documented in the Phase A section above; unchanged and not re-verified this
  phase since Phase D touched no frontend files (last verified 54/54 routes at
  the end of Phase C).

### New, genuine remaining work surfaced by this phase

- **Onboarding flow** (guided first-run dashboard experience) — still not
  built; carried over from the Phase C item above.
- **SMS alert channel** — `sms` exists as a named `AlertChannel` constant with
  an explicit "architecture hook" comment in
  `backend/app/modules/alerts/models.py`, but has no working send
  implementation. No SDK or the CLI can meaningfully use it because the
  backend can't send it.
- **Distributed tracing / metrics dashboards** — `OTEL_EXPORTER_OTLP_ENDPOINT`
  exists as a config setting but no OpenTelemetry instrumentation code exists
  anywhere in the backend. Structured logging is real; tracing/metrics export
  is not wired up.
- **Kubernetes, Nginx, Grafana** — `infra/k8s`, `infra/nginx`, `infra/grafana`
  are empty directories. No manifests, reverse-proxy config, or dashboards
  exist. This was true before Phase D and remains true after it — self-hosting
  today means Docker Compose only (see `docs/self-hosting/README.md`).
- **AI Copilot / AI layer** — no such module exists in `backend/app/modules`.
  Marked "Coming soon" on the marketing Features page since Phase C; still
  accurate.
- **Go/Java SDK mechanical verification** — see Environment limitations above;
  this is the single biggest open item before either SDK should be trusted in
  production.

---

## Phase D closeout — Go verified, onboarding built, honesty re-confirmed

Additive; nothing above was deleted, and this section is intentionally the
up-to-date status where it differs from the Phase D section above. See
`PHASE_D_REPORT.md` for the full account.

### Done this pass

- ✅ **Go SDK is now mechanically verified.** A Go toolchain was installed.
  `go build ./...` failed on a real bug first (`transport.go`, an invalid
  integer-shift-on-float64 expression) — fixed, then `go build` clean,
  `go test ./...` **9/9 passing**, `go vet` clean, `gofmt -l .` found and
  fixed 4 files with cosmetic struct-tag misalignment. **Superseded from the
  "Go/Java SDK mechanical verification" item above: Go's half of that item is
  done.**
- ⚠️ **Java SDK: closer, but still blocked.** A JDK (`javac` 21) and Maven are
  now installed — the "no JDK compiler" half of the earlier limitation no
  longer applies. But Maven Central is still unreachable (403, confirmed
  directly against `repo1.maven.org`), so `mvn compile test` still can't run.
  This is now purely a dependency-access problem, not a missing-tooling one.
- ✅ **Onboarding flow — built.** `apps/web/components/dashboard/onboarding-checklist.tsx`,
  mounted at the top of `/dashboard`. No backend changes: it derives 3 steps
  (API key created, endpoint added, test event sent) from the existing
  `GET /v1/api-keys` / `/v1/endpoints` / `/v1/events` endpoints already used
  by their respective pages. Dismissal/completion state is `localStorage`-only
  (keyed by org id, same tradeoff as token storage) since no backend field
  for it exists — this means it won't persist across devices/browsers for the
  same account, which is a real, documented limitation, not a bug. **This
  fully closes the "Onboarding flow" item above.**
- ✅ **SMS / OpenTelemetry / Kubernetes-Nginx-Grafana / AI layer** — all
  re-inspected against live source this pass rather than trusting the prior
  write-up. All four were already honestly documented as Planned/Not
  implemented on both the backend and frontend/docs side. No changes needed;
  the four bullets above remain accurate as-is.
- ✅ **Final consistency audit (read-only)** — re-checked the earlier
  Phase D schema-drift fix (`AlertRuleOut`/`AlertEventOut`/`TestAlertResponse`,
  billing's `SubscriptionOut`/`UsageOut`/`InvoiceOut`, `analytics.export()`'s
  `report` param) against the live backend schemas and all 4 SDKs. Still
  matches everywhere; no new drift found. The Java SDK's Jackson
  `SNAKE_CASE` global naming strategy correctly maps its camelCase fields to
  the real JSON field names without per-field annotations.

### Updated remaining work before Phase E

1. Run `mvn compile test` for the Java SDK in an environment with real Maven
   Central network access; fix anything that surfaces. (This is now the
   **only** SDK-verification gap — Go's is closed.)
2. (Optional, not required for a genuine onboarding flow) Add a real backend
   field — e.g. an `onboarding_completed_at` column on the organization — if
   cross-device/cross-browser persistence of onboarding-dismissal state is
   wanted. The current client-only implementation is honest and functional,
   just per-browser.
3. SMS alert channel, OpenTelemetry instrumentation, Kubernetes/Nginx/Grafana,
   AI layer remain explicitly out of scope for Phase D, confirmed accurately
   documented this pass.

