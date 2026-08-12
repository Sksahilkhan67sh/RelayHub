# RelayHub API Reference

Base URL: `https://api.relayhub.dev/v1` (self-hosted: `http://localhost:8000/v1` by
default -- see [Self-Hosting Guide](../self-hosting/README.md)).

This reference is generated directly from the FastAPI route definitions in
`backend/app/modules/*/routes.py` -- every endpoint listed here exists in the
code; nothing here is aspirational. If a route isn't in this reference, it isn't
implemented.

## Authentication

Two distinct authentication schemes exist, used by different parts of the API:

1. **Session bearer tokens** -- `Authorization: Bearer <access_token>`, issued by
   `POST /auth/login` or `POST /auth/register`, used by the dashboard and by most
   management endpoints (organizations, endpoints, DLQ, analytics, billing,
   admin, etc). Access tokens are short-lived; refresh with `POST /auth/refresh`.
2. **API keys** -- `Authorization: Bearer <api_key>`, created via
   `POST /api-keys`, used specifically by `POST /events` (publishing events).
   Each key is scoped (e.g. `events:write`) and independently revocable.

Both schemes use the same `Authorization: Bearer <token>` header shape; the
backend distinguishes them by token format.

## RBAC roles

Four roles, enforced server-side on every route (not just hidden in the UI):
`owner` > `admin` > `member` > `viewer`. A route documented as "requires `admin`"
also accepts `owner` (roles are hierarchical). Platform-admin-only routes
(`/admin/*`) are a separate flag (`is_platform_admin` on the user), independent
of organization role.

## Errors

Every non-2xx response follows the same envelope:

```json
{
  "error": {
    "message": "Human-readable description",
    "code": "optional_machine_code",
    "request_id": "optional-request-id"
  }
}
```

| Status | Meaning |
|---|---|
| 400 / 422 | Validation error -- malformed request body or query params |
| 401 | Missing, invalid, or expired credentials |
| 403 | Authenticated, but the role/scope doesn't allow this action |
| 404 | Resource not found (or not visible to this organization) |
| 409 | Conflicting state (duplicate invitation, already-revoked resource, etc) |
| 429 | Rate limited -- see `Retry-After` header |
| 5xx | Server error |

## Rate limiting

Sliding-window-log rate limiting (see `backend/app/common/rate_limiter.py`)
applies to: the login endpoint (IP-based, 10 requests / 5 minutes), the
forgot-password endpoint (IP-based, 5 requests / hour), and API-key-authenticated
event publishing (per-key, limits set by the organization's billing plan --
`rate_limit_per_minute` / `_per_hour` / `_per_day` on the plan). Rate-limited
responses return `429` with a `Retry-After` header.

## Pagination

List endpoints that support pagination take `limit` (default 50, max 200) and
`offset` query params and return a plain JSON array -- there's no envelope or
cursor. To page through a full result set, keep incrementing `offset` by `limit`
until a page comes back shorter than `limit`. Not every list endpoint paginates
-- see each module's reference for which do.

## Idempotency

`POST /events` accepts an `idempotency_key` field in the request body (not a
header). This is the only endpoint with idempotency support in the current
implementation.

## Modules

| Module | Base path | Reference |
|---|---|---|
| Authentication | `/auth` | [auth.md](./auth.md) |
| Organizations & Invitations | `/org`, `/invitations` | [organizations.md](./organizations.md) |
| API Keys | `/api-keys` | [api-keys.md](./api-keys.md) |
| Endpoints | `/endpoints` | [endpoints.md](./endpoints.md) |
| Events | `/events` | [events.md](./events.md) |
| Deliveries & Logs | `/deliveries`, `/logs` | [deliveries.md](./deliveries.md) |
| Dead-Letter Queue | `/dlq` | [dlq.md](./dlq.md) |
| Analytics | `/analytics` | [analytics.md](./analytics.md) |
| Billing | `/billing` | [billing.md](./billing.md) |
| Notifications (Alerts) | `/alerts` | [notifications.md](./notifications.md) |
| Audit Logs | `/audit-logs` | [audit.md](./audit.md) |
| Admin (platform admin only) | `/admin` | [admin.md](./admin.md) |

## Not in this API

- **Projects** -- there is no Projects resource. Endpoints and events belong
  directly to an organization.
- **AI Copilot** -- not implemented (see Features page / Changelog for roadmap status).
- **SDKs as a REST resource** -- SDKs are client libraries (see [`sdks/`](../../sdks)), not an API endpoint.
