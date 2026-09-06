# Admin -- `/admin`

Source: `backend/app/modules/admin/routes.py`

**Every route on this page requires the caller's `is_platform_admin` flag** --
this is a separate, platform-wide flag independent of organization role
(`require_platform_admin` dependency). A regular organization `owner` cannot
call these routes without also being a platform admin.

## GET /admin/organizations

- **Response `200`:** `AdminOrganizationOut[]`
- **Pagination:** `limit` (default 50, max 200), `offset`

## POST /admin/organizations/{id}/suspend

- **Response `200`:** `AdminOrganizationOut` (now suspended -- blocks event delivery and dashboard access for that org)

## POST /admin/organizations/{id}/unsuspend

- **Response `200`:** `ForceActionResponse`

## POST /admin/organizations/{id}/impersonate

Issues a session for support/debugging purposes.

- **Response `200`:** `ImpersonationResponse`

## GET /admin/queues

- **Response `200`:** `QueueDepthOut` -- current Redis queue depth for delivery/retry jobs

## GET /admin/system-health

- **Response `200`:** `SystemHealthOut`. Note: worker/process heartbeat is not
  tracked yet (documented gap, not a fabricated field -- see `REMAINING_WORK.md`
  Tier 3); the response is explicit about this rather than reporting a fake
  `workers: healthy`.

## GET /admin/billing-overview

- **Response `200`:** `BillingOverviewOut` -- platform-wide revenue/plan-distribution summary

## GET /admin/logs

- **Query:** platform-wide log search (mirrors `/logs` but unscoped to one organization)

## POST /admin/delivery-jobs/{jobId}/force-retry

- **Response `200`:** `ForceActionResponse` -- forces a retry outside the normal backoff schedule (support tool)

## POST /admin/delivery-jobs/{jobId}/force-cancel

- **Response `200`:** `ForceActionResponse`

## POST /admin/feature-flags

- **Body:** `CreateFeatureFlagRequest` -- `{ "key": string, "description"?: string, "is_enabled_globally"?: boolean }`
- **Response `201`:** `FeatureFlagOut`

## GET /admin/feature-flags

- **Response `200`:** `FeatureFlagOut[]`

## PATCH /admin/feature-flags/{key}

- **Body:** `{ "description"?: string, "is_enabled_globally"?: boolean }`
- **Response `200`:** `FeatureFlagOut`

## POST /admin/feature-flags/{key}/override

Sets (or updates) a per-organization override that takes precedence over the
global toggle for that one organization.

- **Body:** `SetFeatureFlagOverrideRequest` -- `{ "organization_id": string, "is_enabled": boolean }`
- **Response `200`:** `{ "key", "organization_id", "is_enabled" }`

## GET /admin/feature-flags/{key}/overrides

Added in Phase B specifically so the admin UI could show current override state
instead of writing blind -- see `docs/history/PHASE_B_REPORT.md`.

- **Response `200`:** `FeatureFlagOverrideOut[]` -- includes `organization_name`

## POST /admin/abuse-reports

- **Body:** `CreateAbuseReportRequest`
- **Response `201`:** `AbuseReportOut`

## GET /admin/abuse-reports

- **Query:** `status?`
- **Response `200`:** `AbuseReportOut[]`

## PATCH /admin/abuse-reports/{id}

- **Response `200`:** `AbuseReportOut` -- resolve/update a report
