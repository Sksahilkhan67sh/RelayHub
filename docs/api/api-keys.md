# API Keys -- `/api-keys`

Source: `backend/app/modules/api_keys/routes.py`

API keys authenticate `POST /events` (event publishing) independently of user
session tokens. Only a hash of each key is stored -- the raw key is shown once,
at creation or rotation, and cannot be retrieved again.

## POST /api-keys

- **Auth:** Bearer access token
- **RBAC:** `admin`
- **Body:** `{ "name": string, "environment"?: "test"|"live", "scopes"?: string[], "expires_in_days"?: number }`
- **Response `201`:** `ApiKeyCreatedResponse` -- includes `key` (raw, shown once)
- **Errors:** `422` invalid scopes

```bash
curl -X POST https://api.relayhub.dev/v1/api-keys \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"production","environment":"live","scopes":["events:write"]}'
```
```json
{"id":"key_...","name":"production","environment":"live","scopes":["events:write"],"key_prefix":"rh_live_","key":"rh_live_abc123...","expires_at":null,"created_at":"2026-08-01T00:00:00Z"}
```

## GET /api-keys

- **RBAC:** `admin`
- **Response `200`:** `ApiKeyOut[]` -- each entry includes `masked_key` (e.g. `rh_live_ab...yz`), never the raw key

## POST /api-keys/{id}/revoke

- **RBAC:** `admin`
- **Body:** `{ "reason"?: string }`
- **Response `200`:** `ApiKeyOut` (now revoked -- immediately stops authenticating)

## POST /api-keys/{id}/rotate

Revokes the old key and issues a new one in one call, so a caller doesn't have a
window with no valid key.

- **RBAC:** `admin`
- **Response `200`:** `ApiKeyCreatedResponse` -- `key` shown once, same as create
