package relayhub

import "context"

type AuthService struct{ t *transport }

type RegisterRequest struct {
	Email            string `json:"email"`
	Password         string `json:"password"`
	FullName         string `json:"full_name"`
	OrganizationName string `json:"organization_name"`
}

// Register calls POST /v1/auth/register.
func (s *AuthService) Register(ctx context.Context, req RegisterRequest, opts ...RequestOption) (TokenResponse, error) {
	return decode[TokenResponse](s.t.do(ctx, "POST", "/v1/auth/register", req, opts...))
}

// Login calls POST /v1/auth/login.
func (s *AuthService) Login(ctx context.Context, email, password string, opts ...RequestOption) (TokenResponse, error) {
	body := map[string]string{"email": email, "password": password}
	return decode[TokenResponse](s.t.do(ctx, "POST", "/v1/auth/login", body, opts...))
}

// Refresh calls POST /v1/auth/refresh.
func (s *AuthService) Refresh(ctx context.Context, refreshToken string, opts ...RequestOption) (TokenResponse, error) {
	body := map[string]string{"refresh_token": refreshToken}
	return decode[TokenResponse](s.t.do(ctx, "POST", "/v1/auth/refresh", body, opts...))
}

// Logout calls POST /v1/auth/logout (204 No Content on success).
func (s *AuthService) Logout(ctx context.Context, opts ...RequestOption) error {
	_, err := s.t.do(ctx, "POST", "/v1/auth/logout", nil, opts...)
	return err
}

// Me calls GET /v1/auth/me.
func (s *AuthService) Me(ctx context.Context, opts ...RequestOption) (MeResponse, error) {
	return decode[MeResponse](s.t.do(ctx, "GET", "/v1/auth/me", nil, opts...))
}

// ForgotPassword calls POST /v1/auth/forgot-password. Always returns the same
// generic message whether or not the email is registered, by design.
func (s *AuthService) ForgotPassword(ctx context.Context, email string, opts ...RequestOption) (string, error) {
	body := map[string]string{"email": email}
	resp, err := decode[struct {
		Message string `json:"message"`
	}](s.t.do(ctx, "POST", "/v1/auth/forgot-password", body, opts...))
	return resp.Message, err
}

// ResetPassword calls POST /v1/auth/reset-password (204 No Content on success).
func (s *AuthService) ResetPassword(ctx context.Context, token, newPassword string, opts ...RequestOption) error {
	body := map[string]string{"token": token, "new_password": newPassword}
	_, err := s.t.do(ctx, "POST", "/v1/auth/reset-password", body, opts...)
	return err
}
