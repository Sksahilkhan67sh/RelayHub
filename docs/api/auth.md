# Authentication -- `/auth`

Source: `backend/app/modules/auth/routes.py`

## POST /auth/register

Creates a new user and a new organization (the registering user becomes `owner`).

- **Auth:** none
- **RBAC:** none
- **Rate limit:** none
- **Body:** `{ "email": string, "password": string, "full_name": string, "organization_name": string }`
- **Response `200`:** `TokenResponse` -- `{ "access_token", "refresh_token", "token_type" }`
- **Errors:** `422` invalid input; `409` email already registered

```bash
curl -X POST https://api.relayhub.dev/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","password":"StrongPass1","full_name":"Dev User","organization_name":"Acme"}'
```
```json
{"access_token":"eyJ...","refresh_token":"eyJ...","token_type":"bearer"}
```

## POST /auth/login

- **Auth:** none
- **Rate limit:** IP-based, 10 requests / 5 minutes (`backend/app/modules/auth/dependencies.py`)
- **Body:** `{ "email": string, "password": string }`
- **Response `200`:** `TokenResponse`
- **Errors:** `401` invalid credentials or locked account; `429` rate limited

## POST /auth/refresh

- **Auth:** none (the refresh token itself is the credential)
- **Body:** `{ "refresh_token": string }`
- **Response `200`:** `TokenResponse` -- issues a new access/refresh pair and revokes the old refresh token (rotation)
- **Errors:** `401` invalid, expired, or already-used refresh token

## POST /auth/logout

- **Auth:** Bearer access token required
- **Response `204`:** No Content -- revokes the current refresh token family
- **Errors:** `401`

## GET /auth/me

- **Auth:** Bearer access token required
- **Response `200`:** `MeResponse` -- `{ "user": {...}, "organization": {...}, "role": "owner"|"admin"|"member"|"viewer" }`

```bash
curl https://api.relayhub.dev/v1/auth/me -H "Authorization: Bearer $TOKEN"
```
```json
{"user":{"id":"...","email":"dev@example.com","full_name":"Dev User","is_platform_admin":false},"organization":{"id":"...","name":"Acme","slug":"acme"},"role":"owner"}
```

## POST /auth/forgot-password

- **Auth:** none
- **Rate limit:** IP-based, 5 requests / hour
- **Body:** `{ "email": string }`
- **Response `200`:** `{ "message": string }` -- **always the same generic message**, whether or not the email is registered (deliberate: never confirms account existence). See `PHASE_A_REPORT.md`.
- **Side effect:** if the email matches an active account, a one-time, expiring reset link is emailed.

## POST /auth/reset-password

- **Auth:** none (the reset token is the credential)
- **Body:** `{ "token": string, "new_password": string }`
- **Response `204`:** No Content -- resets the password, invalidates the reset token and any other active reset tokens for that user, and revokes every refresh-token family (forces re-login everywhere).
- **Errors:** `400` invalid, expired, or already-used token
