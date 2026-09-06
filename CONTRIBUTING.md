# Contributing to RelayHub

Practical conventions, not a style manifesto. If something here conflicts
with what the existing code actually does, the existing code wins — file an
issue rather than silently diverging further.

## Before you start

Read [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) and
[`docs/WHERE_TO_MAKE_CHANGES.md`](docs/WHERE_TO_MAKE_CHANGES.md) first. Most
"where does this go" questions are already answered there.

## Branch naming

`<type>/<short-description>`, matching the type prefixes already used in this
repo's history: `fix/`, `feat/`, `chore/`, `docs/`, `test/`, `ci/`,
`style/`. Keep the description a few words, hyphenated.

## Commits

One logical change per commit where reasonable. The commit message should
answer, in order: **what** changed, **why** (the actual root cause if it's a
fix — not just "fixes bug"), and **how it was verified**. Look at this repo's
own git log for the level of detail expected — a commit message that only a
future you, six months from now with zero memory of today, could use to
understand the change without re-reading the diff.

## Where business logic belongs

`routes.py` → `service.py` → (`models.py`/`db/tenant_query.py`). Never in a
route handler, never duplicated inside a Celery task when a service function
already exists for it. If you're about to write the same `if` check in two
places, that's a sign it belongs in a shared service function instead.

## Coding conventions

- **Backend:** type-annotated Python, `ruff` and `mypy` clean (see
  Verification below). Organization-scoped queries go through
  `db.tenant_query.tenant_select(...)`, not a bare `select(...)` — this is
  the actual tenant-isolation mechanism, not a suggestion.
- **Frontend:** TypeScript throughout, no `any` without a specific reason
  documented in a comment. API calls go through `lib/api-client.ts`'s
  `api.*` methods, not raw `fetch()` (the SSE client and the token-refresh
  logic itself are the only established exceptions — both need to bypass the
  normal client for a specific, documented reason).
- **Both:** match the file you're editing's existing style before
  introducing a new one. Consistency with the surrounding code beats a
  personal preference.

## Testing requirements

Every behavior change needs a test that would fail without the fix/feature.
Follow the naming and location convention of the module you're touching
(`backend/tests/integration/test_<module>.py`). Before opening a PR:

```bash
cd backend && pytest -q && ruff check app && mypy app --ignore-missing-imports
cd apps/web && npx tsc --noEmit && npx next lint
```

A test that doesn't assert anything meaningful (or that would pass whether or
not your change is correct) isn't worth adding just to raise a count.

## API change rules

- Adding a new endpoint or a new optional field: fine.
- Renaming/removing a field, changing a status code, or changing
  authentication requirements on an existing endpoint: this is a breaking
  change to every SDK and the frontend simultaneously. Update
  `lib/types.ts` and every SDK in the same PR, or don't make the change
  without discussing it first.
- The realtime event contract (`realtime/events.py`) and the webhook
  signature scheme (`delivery/signing.py`) are the two most expensive things
  to change — a webhook customer's own signature-verification code depends
  on the latter never changing shape.

## Database migration rules

- One migration per PR that needs one; never edit a migration already merged
  to `main` (see `WHERE_TO_MAKE_CHANGES.md`'s migration section for the
  exact steps).
- Every migration needs a working `downgrade()`, not just `upgrade()`.
- Test against real Postgres before merging — SQLite (what the default test
  suite uses) is laxer about constraints and types than Postgres is; that's
  exactly why CI also runs the full suite against a real Postgres service
  container.

## Environment variable rules

- Every setting the backend reads is a field on `Settings` in
  `backend/app/core/config.py` — don't read `os.environ` directly elsewhere.
- Add new variables to `backend/.env.example` (or `apps/web/.env.example`
  for the frontend) in the same PR, with a comment explaining what it's for
  — see `docs/CONFIGURATION.md` for the full current reference.
- A feature that depends on an optional external service (an AI provider, an
  email provider) must fail with a clear, specific error when its config is
  missing — never a silent no-op and never a confusing generic timeout. See
  `common/notification_client.py` and `ai_gateway/gateway.py` for the
  existing pattern.
- Never commit a real `.env`/`.env.local` file — both are `.gitignore`d.

## Security rules

- Cryptographic primitives (hashing, JWT, API key generation) live only in
  `backend/app/core/security.py`. Don't hand-roll them elsewhere.
- Any change to `auth/org_service.py` or `auth/invitation_service.py` that
  touches role assignment must preserve the owner-only guard on
  granting/removing the OWNER role — see
  `tests/integration/test_member_role_escalation.py` for the exact
  behavior that must keep passing.
- Outbound webhook URLs go through the SSRF checks in `endpoints/security.py`
  and `delivery/connect_time_security.py` — don't add a code path that sends
  an HTTP request to a user-supplied URL without going through these.
- Never log secrets, tokens, or full webhook payloads at anything above
  debug level.

## PR expectations

- Describe the actual root cause for a fix, not just the symptom — future
  readers (including future you) need to know *why*, not just *what changed*.
- Include what you ran to verify it (see Testing requirements above) and the
  actual results, not just "tests pass."
- If a change is genuinely risky or you're not confident behavior is fully
  preserved, say so explicitly in the PR rather than presenting uncertain
  work as done.

## How to safely modify shared infrastructure

Files like `db/tenant_query.py`, `auth/dependencies.py` (`require_role`,
`get_current_auth`), `core/security.py`, and `common/notification_client.py`
are depended on by most of the codebase. Before changing one:

1. Grep for every call site first — know the full blast radius before you start.
2. Run the *entire* backend test suite after, not just the module you meant
   to change — a change here is exactly the kind that breaks something
   unrelated silently.
3. Prefer additive changes (a new optional parameter with a safe default)
   over changing existing behavior for existing callers.

## Baseline that must not regress

Backend: all tests passing, `ruff` clean, `mypy` clean.
Frontend: `tsc --noEmit` clean, `next lint` clean.
If your change makes any of these worse, it's not ready — including a
pre-existing failure you didn't cause; flag it instead of merging on top of it.
