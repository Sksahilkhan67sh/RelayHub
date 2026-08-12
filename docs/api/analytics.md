# Analytics -- `/analytics`

Source: `backend/app/modules/analytics/routes.py`

All routes accept the same optional range filters: `environment?`, `start_date?`,
`end_date?` (ISO 8601 dates).

## GET /analytics/summary

- **Auth:** Bearer access token
- **RBAC:** any role
- **Response `200`:** `{ "total_events", "total_deliveries", "success_rate", "p50_latency_ms", "p95_latency_ms", "p99_latency_ms" }`

## GET /analytics/deliveries-over-time

- **RBAC:** any role
- **Query:** range filters, plus `granularity?` (`hour`|`day`)
- **Response `200`:** `{ "bucket", "success_count", "failure_count" }[]`

## GET /analytics/events-by-type

- **RBAC:** any role
- **Response `200`:** `{ "event_type", "count" }[]`

## GET /analytics/top-endpoints

- **RBAC:** any role
- **Response `200`:** `{ "endpoint_id", "endpoint_name", "delivery_count", "failure_rate" }[]`

## GET /analytics/endpoint-health

- **RBAC:** any role
- **Response `200`:** `{ "endpoint_id", "endpoint_name", "health_status", "consecutive_failure_count" }[]`

## GET /analytics/export

CSV export. **`report` is required** -- there is no "export everything" mode.

- **RBAC:** any role
- **Query:** `report` (required: `deliveries-over-time` | `top-endpoints`), plus the standard range filters, plus `granularity?` when `report=deliveries-over-time`
- **Response `200`:** `text/csv` body
- **Errors:** `422` if `report` is missing or not one of the two values

```bash
curl "https://api.relayhub.dev/v1/analytics/export?report=top-endpoints&start_date=2026-07-01&end_date=2026-08-01" \
  -H "Authorization: Bearer $TOKEN"
```
