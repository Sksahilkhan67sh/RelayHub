# RelayHub — Phase A Report

Scope: **Feature 1 (password reset)** and **Feature 2 (team invite email flow)**, backend-
complete, plus the minimum frontend needed to verify each. Nothing else touched.
Existing architecture, DI, tenant isolation, audit logging, rate limiting, and coding
conventions reused throughout — no redesign, no rewrites of completed modules, no
placeholders.

## Files changed

### Backend — new files
- `app/modules/auth/password_reset_service.py` — `request_password_reset` /
  `confirm_password_reset`
- `app/modules/auth/invitation_service.py` — `create_invitation` /
  `get_invitation_by_token` / `accept_invitation` / `revoke_invitation`
- `app/modules/auth/invitation_schemas.py` — `InvitationOut`, `InvitationPublicOut`,
  `AcceptInvitationRequest` (`CreateInvitationRequest` is an alias for the pre-existing
  `InviteUserRequest`, see "Reuse notes" below)
- `app/modules/auth/invitation_routes.py` — public router: `GET /invitations/{token}`,
  `POST /invitations/accept`
- `alembic/versions/0011_password_reset_tokens.py`
- `alembic/versions/0012_invitations.py`
- `tests/integration/test_password_reset.py` — 12 tests
- `tests/integration/test_invitations.py` — 13 tests

### Backend — extended files (no existing logic changed, only additions)
- `app/modules/auth/models.py` — added `PasswordResetToken`, `Invitation` models
- `app/modules/auth/schemas.py` — filled in the previously **unused/dead**
  `ForgotPasswordRequest` / `ResetPasswordRequest` schemas (added
  `ForgotPasswordResponse`, password-complexity validation); nothing existing removed
- `app/modules/auth/dependencies.py` — added `enforce_forgot_password_rate_limit` and
  `get_optional_auth`; refactored the rate-limit body shared with
  `enforce_login_rate_limit` into `_enforce_rate_limit` — behavior and response headers
  for the existing login limiter are unchanged (verified: all pre-existing rate-limit
  tests still pass unmodified)
- `app/modules/auth/routes.py` — added `POST /auth/forgot-password`,
  `POST /auth/reset-password`
- `app/modules/auth/org_routes.py` — added `POST /org/invitations`,
  `POST /org/invitations/{id}/revoke` (org-scoped, admin-only, alongside the existing
  member-management endpoints)
- `app/modules/audit/models.py` — added 5 `AuditAction` values (see below)
- `app/core/security.py` — added `generate_secure_token()`, same "hash before persist"
  pattern as the existing `generate_api_key`/`hash_api_key`
- `app/core/config.py` — added `FRONTEND_URL`, `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`,
  `INVITATION_TOKEN_EXPIRE_DAYS`
- `app/main.py` — registered the new `invitations` router
- `tests/conftest.py` — added an `InMemoryNotificationDispatcher` override to the
  `client` fixture (`client.fake_notifications`), same pattern as the existing
  `fake_stripe` / `fake_queue` / `fake_rate_limiter`

### Frontend — new pages (only what's needed to verify the two backend features)
- `app/(auth)/accept-invitation/page.tsx`
- `app/(auth)/invitation-expired/page.tsx`
- `app/(auth)/invitation-success/page.tsx`
- `app/(auth)/forgot-password/page.tsx`
- `app/(auth)/reset-password/page.tsx`

`forgot-password`/`reset-password` were not explicitly listed under Feature 2's
frontend scope (that list only covers the invite flow), but they're included here
because **the login page already links to `/forgot-password`** — a real, pre-existing
dead link (same class of issue as the `/logs` placeholder from the prior audit pass)
that would otherwise stay broken even though its backend now exists. No other frontend
surface was touched.

## Endpoints added

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/auth/forgot-password` | none | Request a reset link (rate-limited, enumeration-safe) |
| POST | `/v1/auth/reset-password` | none | Consume a reset token, set new password |
| POST | `/v1/org/invitations` | admin+ | Create + email an org invitation |
| GET | `/v1/invitations/{token}` | none | Look up an invitation for the accept page |
| POST | `/v1/invitations/accept` | optional | Accept an invitation (creates account if needed) |
| POST | `/v1/org/invitations/{id}/revoke` | admin+ | Revoke a pending invitation |

## Database changes

- **`password_reset_tokens`**: `id`, `user_id` (FK → users, cascade), `hashed_token`
  (unique, sha256), `expires_at`, `used_at`, `created_at`/`updated_at`. Raw tokens are
  never persisted.
- **`invitations`**: `id`, `organization_id` (FK → organizations, cascade), `email`,
  `role`, `invited_by_user_id` (FK → users), `hashed_token` (unique, sha256),
  `expires_at`, `accepted_at`, `revoked_at`, `created_at`/`updated_at`. Status
  (pending/accepted/revoked/expired) is derived, not stored, from the three timestamp
  columns.

## Design decisions worth flagging

- **Token invalidation**: rather than adding a field beyond the spec's exact list,
  "invalidate previous active reset tokens" is implemented by marking prior unused
  `PasswordResetToken` rows `used_at = now` whenever a new one is issued (and again,
  defensively, whenever one is consumed). Same one-active-token-at-a-time property,
  no schema addition needed.
- **Existing-account collision in accept-invitation**: if an invitation email already
  has a RelayHub account, `POST /invitations/accept` only attaches the membership when
  the caller is authenticated *as that account* (`get_optional_auth`, matched against
  `current_auth.user_id`). Otherwise it returns 409 asking them to log in first. This
  was the one point in the spec with no single obvious answer — the alternative
  (auto-attaching on token possession alone) would let anyone who intercepts an invite
  link attach themselves to an *existing* account with no password check, which is an
  account-takeover primitive. The chosen behavior costs one extra login step for that
  one case; new-invitee signups (the common case) are unaffected and complete in a
  single request.
- **Duplicate/dead schema reuse**: `ForgotPasswordRequest`, `ResetPasswordRequest`, and
  `InviteUserRequest` already existed in `auth/schemas.py`, unused by any route — likely
  scaffolding from an earlier pass that the original audit's dead-code sweep missed.
  Reused as-is (with minor validation additions) rather than creating parallel schemas.
- **Rate limiting**: `/auth/forgot-password` reuses the exact IP-based sliding-window
  `RateLimiter` the login endpoint already uses (5 requests/hour/IP) — same dependency
  injection pattern, no new limiter implementation.
- **Email delivery**: both flows reuse the existing `NotificationDispatcher` DI
  (`channel="email"`) — no new email-sending code path.

## Tests added (25 total, all passing)

**Password reset** (`test_password_reset.py`, 12): forgot-password sends email for a
real account / sends nothing and returns the identical response for an unknown one;
reset succeeds with a valid token and old password stops working; invalid token
rejected; token is one-time-use; expired token rejected; requesting a new reset token
invalidates the previous one; successful reset revokes all refresh tokens (forces
re-login); weak new password rejected (422); forgot-password is rate-limited;
request + completion are both audited.

**Invitations** (`test_invitations.py`, 13): create sends email; create requires
admin; inviting an existing member returns 409; duplicate pending invite returns 409;
`GET` by token returns invitation details; unknown token returns 404; new-invitee
accept creates an account and membership; accept without password/name is rejected for
a new invitee; existing-user accept requires auth as that user (rejected unauthenticated,
succeeds once authenticated); expired invitation rejected; revoked invitation rejected;
revoke requires admin; revoking an already-accepted invitation returns 409; full
lifecycle is audited.

## Verification (re-run after every change, same commands as the prior release checklist)

| Check | Result |
|---|---|
| Backend tests (`pytest -q`) | ✅ **211/211 passed** (186 pre-existing + 25 new) |
| Backend lint (`ruff check app`) | ✅ **0 errors** |
| Backend typecheck (`mypy app --ignore-missing-imports`) | ⚠️ same **10 pre-existing findings**, 0 new (identical set documented in the prior `REMAINING_WORK.md` Tier 3) |
| Frontend typecheck (`tsc --noEmit`) | ✅ **0 errors** (found and fixed one pre-existing `noUncheckedIndexedAccess` narrowing issue in `invitation-expired/page.tsx`) |
| Frontend lint (`next lint`) | ✅ **0 warnings, 0 errors** |
| Frontend production build (`next build`) | ⚠️ same Google Fonts sandbox restriction as before — verified via the identical throwaway-font-swap workaround; **all 31 routes compiled**, including the 5 new pages; real layout.tsx restored unchanged afterward |

## Remaining work (not part of Phase A, left for later phases)

- Frontend: no UI yet for creating/listing/revoking invitations from
  `settings/team` (Tier 2 item, real gap, no backend blocker — the backend for it now
  exists as of this pass)
- The 10 pre-existing mypy findings (SQLAlchemy/Stripe typing friction) — unchanged,
  still documented in `REMAINING_WORK.md`
- Everything else in the original `REMAINING_WORK.md` Tier 1–3 not covered by Feature
  1/2 (command palette, dark-mode toggle, onboarding, landing pages, token storage
  hardening, worker heartbeats, percentile pre-aggregation)

Phase B not started, per instructions.
