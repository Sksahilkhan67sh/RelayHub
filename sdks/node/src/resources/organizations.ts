import type { Transport, RequestOptions } from "../transport.js";
import type { InvitationOut, MemberOut, OrganizationOut, InvitationStatus } from "../types.js";

export class OrganizationsResource {
  constructor(private readonly transport: Transport) {}

  /** PATCH /v1/org -- update the current organization's name. */
  update(params: { name: string }, options?: RequestOptions) {
    return this.transport.request<OrganizationOut>("PATCH", "/v1/org", params, options);
  }

  /** GET /v1/org/members */
  listMembers(options?: RequestOptions) {
    return this.transport.request<MemberOut[]>("GET", "/v1/org/members", undefined, options);
  }

  /** POST /v1/org/members -- adds an existing RelayHub user directly (no email step). For inviting someone with no account yet, use `invitations.create`. */
  addMember(params: { email: string; role?: string }, options?: RequestOptions) {
    return this.transport.request<MemberOut>("POST", "/v1/org/members", params, options);
  }

  /** PATCH /v1/org/members/{userId} -- 204 No Content on success. */
  updateMemberRole(userId: string, params: { role: string }, options?: RequestOptions) {
    return this.transport.request<void>("PATCH", `/v1/org/members/${userId}`, params, options);
  }

  /** DELETE /v1/org/members/{userId} -- 204 No Content on success. */
  removeMember(userId: string, options?: RequestOptions) {
    return this.transport.request<void>("DELETE", `/v1/org/members/${userId}`, undefined, options);
  }

  readonly invitations = {
    /** POST /v1/org/invitations -- emails an invite link; the invitee doesn't need an existing account. */
    create: (params: { email: string; role?: string }, options?: RequestOptions) =>
      this.transport.request<InvitationOut>("POST", "/v1/org/invitations", params, options),

    /** GET /v1/org/invitations?status=... */
    list: (params?: { status?: InvitationStatus }, options?: RequestOptions) =>
      this.transport.request<InvitationOut[]>("GET", "/v1/org/invitations", undefined, { ...options, query: { status: params?.status } }),

    /** POST /v1/org/invitations/{id}/revoke */
    revoke: (invitationId: string, options?: RequestOptions) =>
      this.transport.request<InvitationOut>("POST", `/v1/org/invitations/${invitationId}/revoke`, undefined, options),

    /** GET /v1/invitations/{token} -- public, unauthenticated; used to render an "accept invite" page before login. */
    getByToken: (token: string, options?: RequestOptions) =>
      this.transport.request<{ organization_name: string; email: string; role: string; status: InvitationStatus; expires_at: string }>(
        "GET",
        `/v1/invitations/${token}`,
        undefined,
        options
      ),

    /** POST /v1/invitations/accept -- public; pass `full_name`/`password` only if the invitee has no existing account. */
    accept: (params: { token: string; full_name?: string; password?: string }, options?: RequestOptions) =>
      this.transport.request<{ access_token: string; refresh_token: string; token_type: string }>("POST", "/v1/invitations/accept", params, options),
  };
}
