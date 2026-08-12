# Dead-Letter Queue -- `/dlq`

Source: `backend/app/modules/dlq/routes.py`

Deliveries that exhaust their configured retry budget land here instead of
disappearing. **This is also where "replay" lives** -- there is no separate
top-level `/replay` endpoint; replaying a delivery means retrying a
dead-lettered job.

## GET /dlq

- **Auth:** Bearer access token
- **RBAC:** any role
- **Pagination:** `limit` (default 50, max 200), `offset`
- **Query:** `endpoint_id?`
- **Response `200`:** `DeadLetterJobOut[]` -- includes full payload and attempt history per job

## GET /dlq/{jobId}

- **RBAC:** any role
- **Response `200`:** `DeadLetterJobOut`
- **Errors:** `404`

## POST /dlq/{jobId}/retry

Replays a single dead-lettered delivery as a fresh attempt -- same signed
payload, does not re-trigger the original event elsewhere in your system.

- **RBAC:** `admin`
- **Response `200`:** `{ "id", "status" }`
- **Errors:** `404`; `409` if the job isn't currently dead-lettered

```bash
curl -X POST https://api.relayhub.dev/v1/dlq/dlj_abc123/retry -H "Authorization: Bearer $TOKEN"
```

## POST /dlq/bulk-retry

Replays up to 500 dead-lettered deliveries in one call.

- **RBAC:** `admin`
- **Body:** `{ "job_ids": string[] }` (max 500)
- **Response `200`:** `{ "retried": string[], "skipped": string[] }` -- `skipped` lists ids that weren't eligible (already retried, not found, etc)

## DELETE /dlq/{jobId}

Permanently discards a dead-lettered delivery without replaying it.

- **RBAC:** `admin`
- **Response `204`:** No Content

## GET /dlq/export

CSV export of the current DLQ view.

- **RBAC:** `admin`
- **Query:** `endpoint_id?`
- **Response `200`:** `text/csv` body
