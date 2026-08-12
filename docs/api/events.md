# Events -- `/events`

Source: `backend/app/modules/events/routes.py`

## POST /events

Publishes an event, fanning it out to every endpoint subscribed to that event
type in the given environment. **This is the one route authenticated by API key**
(`Authorization: Bearer <api_key>`) rather than a user session token, and the
key must carry the `events:write` scope.

- **Auth:** API key with `events:write` scope
- **Rate limit:** per-key, governed by the organization's billing plan (`rate_limit_per_minute`/`_per_hour`/`_per_day`)
- **Quota:** blocked with `402`-style error once the plan's monthly delivery limit is reached (no silent overage billing -- see `backend/app/modules/billing/service.py`)
- **Idempotency:** `idempotency_key` field in the body -- republishing with the same key is safe to retry
- **Body:** `{ "event": string, "payload"?: object, "environment"?: "test"|"live", "idempotency_key"?: string }`
- **Response `201`:** `EventOut` -- includes `delivery_jobs` (one summary per subscribed endpoint)
- **Errors:** `401`/`403` invalid or insufficiently-scoped key; `422` invalid event-type format; `429` rate limited; plan-limit error once quota is exhausted

```bash
curl -X POST https://api.relayhub.dev/v1/events \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"event":"payment.success","payload":{"order_id":"ord_123","amount":4200},"idempotency_key":"ord_123-payment-success"}'
```
```json
{"id":"evt_...","event":"payment.success","environment":"live","payload":{"order_id":"ord_123","amount":4200},"request_id":"req_...","created_at":"2026-08-01T00:00:00Z","delivery_jobs":[{"id":"job_...","endpoint_id":"ep_...","status":"queued"}]}
```

## GET /events/{id}

- **Auth:** Bearer access token
- **RBAC:** any role
- **Response `200`:** `EventOut`
- **Errors:** `404`

## GET /events

- **Auth:** Bearer access token
- **RBAC:** any role
- **Response `200`:** `EventOut[]`
