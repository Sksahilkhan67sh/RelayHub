# Audit Logs -- `/audit-logs`

Source: `backend/app/modules/audit/routes.py`

Every sensitive account action (membership changes, API key creation/revocation,
role changes, settings updates, invitation lifecycle, password resets) is
recorded with actor, action, resource, IP address, and timestamp.

## GET /audit-logs

- **Auth:** Bearer access token
- **RBAC:** `admin`
- **Pagination:** `limit` (default 50, max 200), `offset`
- **Response `200`:** `AuditLogOut[]` -- `{ "id", "actor_user_id", "action", "resource_type", "resource_id", "metadata", "ip_address", "created_at" }`

Note: password-reset audit entries (`auth.password_reset_requested`,
`auth.password_reset_completed`) are recorded with `organization_id = null`
(the request happens before any org context is known) and so do not appear in
this org-scoped listing.
