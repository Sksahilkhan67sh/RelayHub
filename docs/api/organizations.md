# Organizations & Invitations -- `/org`, `/invitations`

Source: `backend/app/modules/auth/org_routes.py`, `backend/app/modules/auth/invitation_routes.py`

All `/org/*` routes operate on the caller's own organization (there is no
cross-organization access; tenant isolation is enforced at the query layer).

## PATCH /org

- **Auth:** Bearer access token
- **RBAC:** `admin`
- **Body:** `{ "name": string }`
- **Response `200`:** `OrganizationOut`

## GET /org/members

- **Auth:** Bearer access token
- **RBAC:** any role
- **Response `200`:** `MemberOut[]`

## POST /org/members

Adds an **existing** RelayHub user directly (no email step). For inviting
someone with no account yet, use `POST /org/invitations` instead.

- **RBAC:** `admin`
- **Body:** `{ "email": string, "role"?: "admin"|"member"|"viewer" }`
- **Response `201`:** `MemberOut`
- **Errors:** `404` no account exists for that email; `409` already a member

## PATCH /org/members/{userId}

- **RBAC:** `admin`
- **Body:** `{ "role": string }`
- **Response `204`:** No Content

## DELETE /org/members/{userId}

- **RBAC:** `admin`
- **Response `204`:** No Content

## POST /org/invitations

Emails an invite link. The invitee does **not** need an existing account --
accepting the invite creates one.

- **RBAC:** `admin`
- **Body:** `{ "email": string, "role"?: "admin"|"member"|"viewer" }`
- **Response `201`:** `InvitationOut`
- **Errors:** `409` already a member, or a pending invitation already exists for that email

```bash
curl -X POST https://api.relayhub.dev/v1/org/invitations \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"email":"new-hire@example.com","role":"member"}'
```

## GET /org/invitations

- **RBAC:** `admin`
- **Query:** `status?` -- `pending` | `accepted` | `revoked` | `expired`
- **Response `200`:** `InvitationOut[]`

## POST /org/invitations/{id}/revoke

- **RBAC:** `admin`
- **Response `200`:** `InvitationOut` (status now `revoked`)
- **Errors:** `409` already accepted or already revoked

## GET /invitations/{token}

Public -- no authentication. Used to render an "accept invite" page before login.

- **Response `200`:** `{ "organization_name", "email", "role", "status", "expires_at" }`
- **Errors:** `404` token doesn't match any invitation

## POST /invitations/accept

Public, but recognizes an existing session: if the caller sends a valid
`Authorization` header for a user whose email matches the invitation, the
membership is attached directly; otherwise `full_name`/`password` are required
to create a new account.

- **Body:** `{ "token": string, "full_name"?: string, "password"?: string }`
- **Response `200`:** `TokenResponse` -- logs the (now-member) user in
- **Errors:** `400` new account requested without `full_name`/`password`; `409` invitation not pending, or an account already exists for that email and the caller isn't authenticated as it
