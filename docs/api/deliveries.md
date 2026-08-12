# Deliveries & Delivery Logs -- `/deliveries`, `/logs`

Source: `backend/app/modules/delivery/routes.py`, `backend/app/modules/logs/routes.py`

A delivery job is one endpoint's attempt history for one event. `/logs` is the
searchable, filterable read model backing the dashboard's Logs page -- prefer it
over `/deliveries` for browsing; use `/deliveries/{id}` when you already have a
specific job id (e.g. from an `EventOut.delivery_jobs` entry).

## GET /deliveries/{jobId}

- **Auth:** Bearer access token
- **RBAC:** any role
- **Response `200`:** `DeliveryJobOut` -- includes the full `attempts[]` history
- **Errors:** `404`

## GET /deliveries/by-event/{eventId}

Every delivery job (one per subscribed endpoint) produced by a single event.

- **RBAC:** any role
- **Response `200`:** `DeliveryJobOut[]`

## GET /logs

The delivery log explorer: every attempt, filterable and paginated.

- **RBAC:** any role
- **Pagination:** `limit` (default 50, max 200), `offset`
- **Query:** `endpoint_id?`, `status?` (repeatable -- `queued`|`processing`|`success`|`retrying`|`failed`|`dead_letter`|`pending`), `event_type?`, `environment?`, `request_id?`, `worker_id?`, `queued_after?`, `queued_before?` (ISO 8601), `min_latency_ms?`, `max_latency_ms?`
- **Response `200`:** `DeliveryLogEntryOut[]`

```bash
curl "https://api.relayhub.dev/v1/logs?status=failed&status=retrying&limit=20" \
  -H "Authorization: Bearer $TOKEN"
```
