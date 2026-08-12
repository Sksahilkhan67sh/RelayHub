# Notifications (Alerts) -- `/alerts`

Source: `backend/app/modules/alerts/routes.py`

**There is no `/notifications` route in the backend.** RelayHub's actual
notification mechanism is alert rules -- Slack, Discord, webhook, or email
notifications fired when a condition (endpoint down, DLQ spike, high latency,
etc) crosses a threshold you configure. This page and the SDKs use
"notifications" as the developer-facing name for this feature; every path below
is the real, implemented `/alerts/*` route.

Valid `condition_type` values: `endpoint_down`, `queue_full`, `dlq_spike`,
`api_key_leak_suspicion`, `high_latency`, `repeated_failures`,
`billing_threshold`, `rate_limit_abuse`.

Valid `severity` values: `info`, `warning`, `critical`.

Valid `channel` values: `email`, `slack`, `discord`, `webhook`. (`sms` exists as
a documented architecture hook in `common/notification_client.py` but has no
working implementation -- see `REMAINING_WORK.md`.)

## POST /alerts/rules

- **Auth:** Bearer access token
- **RBAC:** `admin`
- **Body:** `{ "condition_type": string, "severity"?: string, "channel": string, "channel_config": object, "threshold_config"?: object, "throttle_window_minutes"?: number, "is_enabled"?: boolean }`
- **Response `201`:** `AlertRuleOut`

```bash
curl -X POST https://api.relayhub.dev/v1/alerts/rules \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"condition_type":"endpoint_down","severity":"critical","channel":"slack","channel_config":{"webhook_url":"https://hooks.slack.com/..."}}'
```

## GET /alerts/rules

- **RBAC:** any role
- **Response `200`:** `AlertRuleOut[]`

## PATCH /alerts/rules/{id}

- **RBAC:** `admin`
- **Body:** any subset of `severity`, `channel`, `channel_config`, `threshold_config`, `throttle_window_minutes`, `is_enabled`
- **Response `200`:** `AlertRuleOut`

## DELETE /alerts/rules/{id}

- **RBAC:** `admin`
- **Response `204`:** No Content

## POST /alerts/rules/{id}/test

Fires a test notification through the rule's configured channel immediately,
without waiting for the real condition to occur.

- **RBAC:** `admin`
- **Response `200`:** `TestAlertResponse` -- `{ "delivery_status", "delivery_error" }`

## GET /alerts/history

- **RBAC:** any role
- **Query:** `condition_type?`, `limit?` (default 50, max 200), `offset?`
- **Response `200`:** `AlertEventOut[]` -- each entry includes `delivery_status`/`delivery_error` for whether the notification itself was successfully sent
