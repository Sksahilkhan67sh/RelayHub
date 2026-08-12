package relayhub

import "context"

type OrganizationsService struct {
	t           *transport
	Invitations *InvitationsService
}

func newOrganizationsService(t *transport) *OrganizationsService {
	return &OrganizationsService{t: t, Invitations: &InvitationsService{t: t}}
}

// Update calls PATCH /v1/org.
func (s *OrganizationsService) Update(ctx context.Context, name string, opts ...RequestOption) (Organization, error) {
	body := map[string]string{"name": name}
	return decode[Organization](s.t.do(ctx, "PATCH", "/v1/org", body, opts...))
}

// ListMembers calls GET /v1/org/members.
func (s *OrganizationsService) ListMembers(ctx context.Context, opts ...RequestOption) ([]Member, error) {
	return decode[[]Member](s.t.do(ctx, "GET", "/v1/org/members", nil, opts...))
}

// AddMember calls POST /v1/org/members -- adds an existing RelayHub user
// directly. For inviting someone with no account yet, use Invitations.Create.
func (s *OrganizationsService) AddMember(ctx context.Context, email, role string, opts ...RequestOption) (Member, error) {
	body := map[string]string{"email": email, "role": role}
	return decode[Member](s.t.do(ctx, "POST", "/v1/org/members", body, opts...))
}

// UpdateMemberRole calls PATCH /v1/org/members/{userId} (204 No Content on success).
func (s *OrganizationsService) UpdateMemberRole(ctx context.Context, userID, role string, opts ...RequestOption) error {
	body := map[string]string{"role": role}
	_, err := s.t.do(ctx, "PATCH", "/v1/org/members/"+userID, body, opts...)
	return err
}

// RemoveMember calls DELETE /v1/org/members/{userId} (204 No Content on success).
func (s *OrganizationsService) RemoveMember(ctx context.Context, userID string, opts ...RequestOption) error {
	_, err := s.t.do(ctx, "DELETE", "/v1/org/members/"+userID, nil, opts...)
	return err
}

type InvitationsService struct{ t *transport }

// Create calls POST /v1/org/invitations -- emails an invite link; the invitee
// doesn't need an existing account.
func (s *InvitationsService) Create(ctx context.Context, email, role string, opts ...RequestOption) (Invitation, error) {
	body := map[string]string{"email": email, "role": role}
	return decode[Invitation](s.t.do(ctx, "POST", "/v1/org/invitations", body, opts...))
}

// List calls GET /v1/org/invitations. Pass status = "" to list every status.
func (s *InvitationsService) List(ctx context.Context, status string, opts ...RequestOption) ([]Invitation, error) {
	if status != "" {
		opts = append(opts, WithQuery("status", status))
	}
	return decode[[]Invitation](s.t.do(ctx, "GET", "/v1/org/invitations", nil, opts...))
}

// Revoke calls POST /v1/org/invitations/{id}/revoke.
func (s *InvitationsService) Revoke(ctx context.Context, invitationID string, opts ...RequestOption) (Invitation, error) {
	return decode[Invitation](s.t.do(ctx, "POST", "/v1/org/invitations/"+invitationID+"/revoke", nil, opts...))
}

// InvitationPublic is the minimal, unauthenticated view returned by GetByToken.
type InvitationPublic struct {
	OrganizationName string `json:"organization_name"`
	Email            string `json:"email"`
	Role             string `json:"role"`
	Status           string `json:"status"`
	ExpiresAt        string `json:"expires_at"`
}

// GetByToken calls GET /v1/invitations/{token} -- public, unauthenticated; used
// to render an "accept invite" page before login.
func (s *InvitationsService) GetByToken(ctx context.Context, token string, opts ...RequestOption) (InvitationPublic, error) {
	return decode[InvitationPublic](s.t.do(ctx, "GET", "/v1/invitations/"+token, nil, opts...))
}

// AcceptRequest's FullName/Password are only required when the invitee has no existing RelayHub account.
type AcceptRequest struct {
	Token    string `json:"token"`
	FullName string `json:"full_name,omitempty"`
	Password string `json:"password,omitempty"`
}

// Accept calls POST /v1/invitations/accept -- public.
func (s *InvitationsService) Accept(ctx context.Context, req AcceptRequest, opts ...RequestOption) (TokenResponse, error) {
	return decode[TokenResponse](s.t.do(ctx, "POST", "/v1/invitations/accept", req, opts...))
}
