from __future__ import annotations

from typing import Any

from ..http import RequestOptions, Transport
from ..types import InvitationOut, InvitationStatus, MemberOut, OrganizationOut, TokenResponse


class InvitationsResource:
    """`organizations.invitations` -- email-based invites (see PHASE_A_REPORT.md)."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def create(self, *, email: str, role: str = "member", options: RequestOptions | None = None) -> InvitationOut:
        """POST /v1/org/invitations -- emails an invite link; the invitee doesn't need an existing account."""
        return self._transport.request("POST", "/v1/org/invitations", {"email": email, "role": role}, options)

    def list(self, *, status: InvitationStatus | None = None, options: RequestOptions | None = None) -> list[InvitationOut]:
        """GET /v1/org/invitations?status=..."""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), "status": status}
        return self._transport.request("GET", "/v1/org/invitations", None, opts)

    def revoke(self, invitation_id: str, options: RequestOptions | None = None) -> InvitationOut:
        """POST /v1/org/invitations/{id}/revoke"""
        return self._transport.request("POST", f"/v1/org/invitations/{invitation_id}/revoke", None, options)

    def get_by_token(self, token: str, options: RequestOptions | None = None) -> dict[str, Any]:
        """GET /v1/invitations/{token} -- public, unauthenticated; used to render an "accept invite" page before login."""
        return self._transport.request("GET", f"/v1/invitations/{token}", None, options)

    def accept(
        self, *, token: str, full_name: str | None = None, password: str | None = None, options: RequestOptions | None = None
    ) -> TokenResponse:
        """POST /v1/invitations/accept -- public; pass full_name/password only if the invitee has no existing account."""
        body = {"token": token, "full_name": full_name, "password": password}
        return self._transport.request("POST", "/v1/invitations/accept", body, options)


class OrganizationsResource:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self.invitations = InvitationsResource(transport)

    def update(self, *, name: str, options: RequestOptions | None = None) -> OrganizationOut:
        """PATCH /v1/org -- update the current organization's name."""
        return self._transport.request("PATCH", "/v1/org", {"name": name}, options)

    def list_members(self, options: RequestOptions | None = None) -> list[MemberOut]:
        """GET /v1/org/members"""
        return self._transport.request("GET", "/v1/org/members", None, options)

    def add_member(self, *, email: str, role: str = "member", options: RequestOptions | None = None) -> MemberOut:
        """POST /v1/org/members -- adds an existing RelayHub user directly. For inviting someone with no account, use `invitations.create`."""
        return self._transport.request("POST", "/v1/org/members", {"email": email, "role": role}, options)

    def update_member_role(self, user_id: str, *, role: str, options: RequestOptions | None = None) -> None:
        """PATCH /v1/org/members/{userId} -- 204 No Content on success."""
        return self._transport.request("PATCH", f"/v1/org/members/{user_id}", {"role": role}, options)

    def remove_member(self, user_id: str, options: RequestOptions | None = None) -> None:
        """DELETE /v1/org/members/{userId} -- 204 No Content on success."""
        return self._transport.request("DELETE", f"/v1/org/members/{user_id}", None, options)
