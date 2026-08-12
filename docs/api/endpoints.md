# Endpoints -- `/endpoints`

Source: `backend/app/modules/endpoints/routes.py`

An endpoint is a URL plus delivery configuration: subscribed event types, custom
headers, timeout, retry limit, and an optional IP allowlist.

## POST /endpoints

- **Auth:** Bearer access token
- **RBAC:** `admin`
- **Body:** `{ "name": string, "url": string, "description"?: string, "environment"?: "test"|"live", "custom_headers"?: object, "timeout_seconds"?: number, "subscribed_event_types"?: string[], "ip_allowlist"?: string[], "tls_verification_enabled"?: boolean, "max_retry_attempts"?: number }`
- **Response `201`:** `EndpointOut`
- **Errors:** `422` invalid URL or config

```bash
curl -X POST https://api.relayhub.dev/v1/endpoints \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Prod webhook","url":"https://api.example.com/hooks/relayhub","environment":"live","subscribed_event_types":["payment.success"]}'
```

## GET /endpoints

- **RBAC:** any role
- **Response `200`:** `EndpointOut[]`

## GET /endpoints/{id}

- **RBAC:** any role
- **Response `200`:** `EndpointOut`
- **Errors:** `404`

## PATCH /endpoints/{id}

- **RBAC:** `admin`
- **Body:** any subset of the create fields, plus `is_active?: boolean`
- **Response `200`:** `EndpointOut`

## DELETE /endpoints/{id}

- **RBAC:** `admin`
- **Response `204`:** No Content

## POST /endpoints/{id}/rotate-secret

Returns the new signing secret once, here. `grace_period_hours` keeps the old
secret valid in parallel so in-flight signature verification on the receiving
end doesn't break mid-rotation.

- **RBAC:** `admin`
- **Body:** `{ "grace_period_hours"?: number }`
- **Response `200`:** `EndpointSecretOut` -- `{ "id", "secret", "grace_period_ends_at", "created_at" }`
