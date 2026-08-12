package dev.relayhub.sdk;

import java.util.List;
import java.util.Map;

public final class OrganizationsResource {
    private final Transport transport;
    private final InvitationsResource invitations;

    OrganizationsResource(Transport transport) {
        this.transport = transport;
        this.invitations = new InvitationsResource(transport);
    }

    public InvitationsResource invitations() { return invitations; }

    /** PATCH /v1/org -- update the current organization's name. */
    public Models.Organization update(String name) { return update(name, null); }
    public Models.Organization update(String name, RequestOptions options) {
        return transport.request("PATCH", "/v1/org", Map.of("name", name), Models.Organization.class, options);
    }

    /** GET /v1/org/members */
    public List<Models.Member> listMembers() { return listMembers(null); }
    public List<Models.Member> listMembers(RequestOptions options) {
        return transport.requestList("GET", "/v1/org/members", null, Models.Member.class, options);
    }

    /** POST /v1/org/members -- adds an existing RelayHub user directly. For inviting someone with no account, use invitations().create(). */
    public Models.Member addMember(String email, String role) { return addMember(email, role, null); }
    public Models.Member addMember(String email, String role, RequestOptions options) {
        return transport.request("POST", "/v1/org/members", Map.of("email", email, "role", role), Models.Member.class, options);
    }

    /** PATCH /v1/org/members/{userId} -- 204 No Content on success. */
    public void updateMemberRole(String userId, String role) { updateMemberRole(userId, role, null); }
    public void updateMemberRole(String userId, String role, RequestOptions options) {
        transport.request("PATCH", "/v1/org/members/" + userId, Map.of("role", role), Void.class, options);
    }

    /** DELETE /v1/org/members/{userId} -- 204 No Content on success. */
    public void removeMember(String userId) { removeMember(userId, null); }
    public void removeMember(String userId, RequestOptions options) {
        transport.request("DELETE", "/v1/org/members/" + userId, null, Void.class, options);
    }

    public static final class InvitationsResource {
        private final Transport transport;

        InvitationsResource(Transport transport) { this.transport = transport; }

        /** POST /v1/org/invitations -- emails an invite link; the invitee doesn't need an existing account. */
        public Models.Invitation create(String email, String role) { return create(email, role, null); }
        public Models.Invitation create(String email, String role, RequestOptions options) {
            return transport.request("POST", "/v1/org/invitations", Map.of("email", email, "role", role), Models.Invitation.class, options);
        }

        /** GET /v1/org/invitations?status=... -- pass status = null to list every status. */
        public List<Models.Invitation> list(String status) { return list(status, null); }
        public List<Models.Invitation> list(String status, RequestOptions options) {
            RequestOptions.Builder b = RequestOptions.builder();
            if (options != null) {
                options.headers.forEach(b::header);
                options.query.forEach(b::query);
            }
            if (status != null) b.query("status", status);
            return transport.requestList("GET", "/v1/org/invitations", null, Models.Invitation.class, b.build());
        }

        /** POST /v1/org/invitations/{id}/revoke */
        public Models.Invitation revoke(String invitationId) { return revoke(invitationId, null); }
        public Models.Invitation revoke(String invitationId, RequestOptions options) {
            return transport.request("POST", "/v1/org/invitations/" + invitationId + "/revoke", null, Models.Invitation.class, options);
        }

        /** GET /v1/invitations/{token} -- public, unauthenticated; used to render an "accept invite" page before login. */
        public Models.InvitationPublic getByToken(String token) { return getByToken(token, null); }
        public Models.InvitationPublic getByToken(String token, RequestOptions options) {
            return transport.request("GET", "/v1/invitations/" + token, null, Models.InvitationPublic.class, options);
        }

        public static final class AcceptRequest {
            public String token, fullName, password;
            public AcceptRequest(String token) { this.token = token; }
        }

        /** POST /v1/invitations/accept -- public; set fullName/password only if the invitee has no existing account. */
        public Models.TokenResponse accept(AcceptRequest req) { return accept(req, null); }
        public Models.TokenResponse accept(AcceptRequest req, RequestOptions options) {
            return transport.request("POST", "/v1/invitations/accept", req, Models.TokenResponse.class, options);
        }
    }
}
