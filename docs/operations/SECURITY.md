# RelayHub Security

What's implemented, what was audited and found already correct, and what
remains open. Written from the real code, with findings classified honestly
-- most of the Phase 4 audit found existing protections already in place,
and this document says so rather than claiming credit for them.

---

## Authentication

- **Passwords**: bcrypt via passlib. Never logged, never returned in any API
  response.
- **JWT**: short-lived access tokens + refresh-token families (see
  `refresh_token_families` table, migration 0001). Expiry enforced;
  malformed/expired tokens are rejected by `get_current_auth` before any
  handler runs.
- **API keys**: stored as SHA-256 hashes (`api_keys.key_hash`), never
  plaintext. Only a short `key_prefix` is retained for display. The full key
  is shown exactly once at creation, never retrievable afterwards.
- **GitHub OAuth**: supported (migration 0019).
- **Organization context is never client-supplied.** `AuthContext.organization_id`
  is derived from the authenticated credential (JWT claim or API key row),
  never from a request body, query parameter, or header. This is the single
  most important tenant-isolation property in the system.

## Multi-tenant isolation

**Structural, not per-endpoint discipline.** Every tenant-scoped query goes
through `app/db/tenant_query.py`'s `tenant_select()` helper, and CI runs a
static-analysis lint (`tests/unit/test_tenant_isolation_lint.py`) that fails
the build if a raw, unscoped query is introduced against a tenant-owned
table. That means isolation is enforced at build time, not just by review.

Cross-tenant regression coverage exists for: deliveries and DLQ
(`test_reliability_phase1_e2e.py`, Phase 1), insights and Copilot
(`test_insights_api.py`, `test_copilot_api.py`), realtime streams
(`test_realtime_stream.py`), and -- added in Phase 4 -- rate limiting
(`test_phase4_security_hardening.py`, proving one tenant exhausting its
replay budget cannot deny service to another).

**Admin exceptions** are intentional and narrow: platform-admin endpoints
(`is_platform_admin` on the user row) can read cross-organization
operational data (queue depth, worker health) by design, for operating the
platform. These are operational aggregates, not tenant payload data.

## Authorization / RBAC

Role hierarchy (`VIEWER < MEMBER < ADMIN < OWNER`) enforced server-side via
`require_role(minimum_role)` as a FastAPI dependency -- never in the
frontend alone. Notable assignments: DLQ replay/delete require `ADMIN`; DLQ
read and export require `VIEWER`; platform-admin operations require the
separate `is_platform_admin` flag.

## Rate limiting

Redis-backed **sliding-window log** (`app/common/rate_limiter.py`) --
deliberately not a fixed-window counter, which would let a client burst to
2x the limit across a window boundary.

| Surface | Limit | Scope |
|---|---|---|
| API-key event ingestion | Plan-derived (minute/hour/day tiers), with a per-key minute override | Per API key |
| Login / password reset | Existing limits in `auth/routes.py` | Per identifier |
| Copilot chat | 20 / hour | Per organization |
| **DLQ replay** (added Phase 4) | 60 / minute | Per organization |
| **DLQ bulk-replay** (added Phase 4) | 10 / minute | Per organization |
| **DLQ export** (added Phase 4) | 10 / minute | Per organization |

**Phase 4 finding (HIGH)**: DLQ replay endpoints previously had *no* rate
limit, despite `bulk-retry` re-enqueueing up to 500 delivery jobs per call
(bounded by `BulkRetryRequest.job_ids`'s `max_length=500`). A caller, or a
buggy client in a loop, could saturate the delivery queue with replays.
Now limited per organization via `app/common/route_rate_limit.py`, a thin
dependency wrapper over the existing limiter (no second rate-limiting
system introduced). Limits are set generously enough that an operator
working through a real DLQ backlog after an outage will not hit them.

**Rate-limit key cardinality** is bounded: keys are
`{fixed-bucket-string}:{organization_id}`. No user input, URL, event ID, or
delivery ID ever becomes part of a key.

**Redis-outage behavior**: fail-closed. If Redis is unavailable, the limiter
raises and the request fails rather than silently allowing unlimited
traffic. This matches the pre-existing behavior of the API-key and Copilot
limits -- a deliberate tradeoff for abuse protection on expensive
operations, not an accident. Note the asymmetry with the rest of the
system: a Redis outage already degrades new-delivery dispatch anyway (see
`docs/operations/OBSERVABILITY.md`), so this does not create a new
single-point-of-failure that didn't already exist.

## Request size / resource limits

- Body size: `BodySizeLimitMiddleware` (`app/middleware/body_size_limit.py`),
  applied to every request, rejecting oversized bodies before they reach
  handler or database logic.
- Pagination: list endpoints bound `limit` via Pydantic `Query(le=...)`
  constraints (e.g. DLQ list caps at 200).
- Bulk replay: `max_length=500` on `job_ids`.
- Copilot message size: bounded in `CopilotChatRequest`.

## SSRF protection

Webhook destinations are validated at **connect time**, not only at
endpoint-creation time -- `delivery/executor.py` calls
`resolve_and_validate(url)` immediately before the outbound request, which
resolves the hostname and rejects private/loopback/link-local/metadata
addresses. Validating at connect time (rather than trusting a check
performed when the endpoint was saved) is what closes the DNS-rebinding
window, where a hostname resolves to a public IP at save time and a private
one later.

Per-endpoint `ip_allowlist` and `tls_verification_enabled` fields provide
additional per-tenant control.

## Webhook signing

HMAC-SHA256 over a precisely-defined signing string, with a timestamp and
nonce for replay protection, and constant-time comparison. Secrets are
stored encrypted (`endpoint_secrets.encrypted_secret`, Fernet, keyed by
`ENCRYPTION_MASTER_KEY`) and support rotation with a grace period
(`grace_period_ends_at`). Secrets are never logged and never returned by any
API response after creation.

**The signing contract was not changed in Phase 4** -- any change there
would break every deployed customer verifier, so it's treated as a frozen
public contract.

## Security response headers

`SecurityHeadersMiddleware` sets, on every response: `X-Content-Type-Options:
nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
strict-origin-when-cross-origin`, `Permissions-Policy` (camera/microphone/
geolocation denied), `X-Permitted-Cross-Domain-Policies: none`, and (in
production only) HSTS with a two-year max-age, `includeSubDomains`, and
`preload`.

No `Content-Security-Policy` is set by the API. This is **intentional and
correct for a JSON API** -- CSP governs how a *browser* renders a document,
and belongs on the Next.js frontend's own responses, not on API JSON. Not
adding a CSP here is a deliberate decision, not an oversight; adding one to
the frontend is reasonable follow-up work but was out of scope for this
phase (it requires testing every page for breakage, per the brief's own
warning not to blindly apply headers).

## CORS

Configured via `CORS_ORIGINS` (`app/core/config.py`), an explicit allowlist
-- **not** wildcard origin reflection. Default is `["http://localhost:3000"]`
for local development; production must set this explicitly to the real
frontend origin.

## Error responses

No stack trace, SQL error, filesystem path, internal URL, or secret is ever
returned to an API client. `app/core/error_handlers.py` returns a structured
envelope with a safe error code and message; full tracebacks go to the
server-side structured log only (see `docs/operations/OBSERVABILITY.md`).

## Dependency security

`pip-audit` run against `backend/requirements.txt` during Phase 4 found real
vulnerabilities. Fixed (each verified against the full 461-test suite after
upgrade):

| Package | From | To | Why |
|---|---|---|---|
| PyJWT | 2.9.0 | 2.13.0 | Multiple advisories; this library validates every access token |
| cryptography | 43.0.1 | 50.0.1 | Multiple advisories; backs webhook-secret encryption |
| python-multipart | 0.0.9 | 0.0.31 | Multiple advisories in form parsing |
| fastapi | 0.115.0 | 0.115.14 | Pulls a newer starlette (0.38.6 → 0.46.2), clearing several starlette advisories |

**Still open, documented rather than forced:**

- **starlette**: fully clearing its remaining advisories requires starlette
  ≥1.0, which FastAPI 0.115.x does not support -- it would require a major
  FastAPI upgrade. Deferred deliberately: the brief prohibits uncontrolled
  mass upgrades, and a FastAPI major-version jump needs its own dedicated
  testing pass. **Recommended as a scoped follow-up task.**
- **Next.js 14.2.35** (frontend): `npm audit` reports advisories whose only
  remediation is Next.js 16 -- a two-major-version jump that `npm audit`
  itself flags as breaking. 14.2.35 is already the latest 14.x patch, so
  there is no non-breaking fix available. **Recommended as a scoped
  follow-up task**, not attempted here.
- **pytest / protobuf**: dev/transitive-only, not in the production request
  path.

## Container hardening

`backend/Dockerfile` already runs as a non-root user (`appuser`), uses a
slim base image (`python:3.12-slim`), installs no unnecessary packages,
bakes in no secrets, and declares a `HEALTHCHECK` against `/health/live`.
Audited in Phase 4, no changes needed.

## CI/CD security

All six GitHub Actions workflows already declare explicit `permissions:`
blocks (least-privilege) -- audited in Phase 4, no changes needed. Secrets
are referenced via `${{ secrets.* }}` and never echoed; the backup
workflow's failure path deliberately sanitizes stderr before surfacing it
(see `docs/operations/DATABASE_RECOVERY.md`).

## Known limitations

- starlette and Next.js advisories remain open pending major-version
  upgrades (above).
- No CSP on the frontend (above).
- No automated dependency scanning in CI. `pip-audit` and `npm audit` were
  run manually during this phase; wiring them into CI as a non-blocking job
  would be reasonable follow-up work.
- Production verification of Phase 4 changes: **NOT VERIFIED** -- not yet
  deployed at time of writing.
