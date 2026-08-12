package relayhub

import "context"

type APIKeysService struct{ t *transport }

type CreateAPIKeyRequest struct {
	Name          string   `json:"name"`
	Environment   string   `json:"environment,omitempty"`
	Scopes        []string `json:"scopes,omitempty"`
	ExpiresInDays *int     `json:"expires_in_days,omitempty"`
}

// Create calls POST /v1/api-keys. The full Key is only ever present on this
// response -- store it now, it can't be retrieved again.
func (s *APIKeysService) Create(ctx context.Context, req CreateAPIKeyRequest, opts ...RequestOption) (APIKeyCreated, error) {
	return decode[APIKeyCreated](s.t.do(ctx, "POST", "/v1/api-keys", req, opts...))
}

// List calls GET /v1/api-keys.
func (s *APIKeysService) List(ctx context.Context, opts ...RequestOption) ([]APIKey, error) {
	return decode[[]APIKey](s.t.do(ctx, "GET", "/v1/api-keys", nil, opts...))
}

// Revoke calls POST /v1/api-keys/{id}/revoke.
func (s *APIKeysService) Revoke(ctx context.Context, keyID string, reason string, opts ...RequestOption) (APIKey, error) {
	body := map[string]string{"reason": reason}
	return decode[APIKey](s.t.do(ctx, "POST", "/v1/api-keys/"+keyID+"/revoke", body, opts...))
}

// Rotate calls POST /v1/api-keys/{id}/rotate -- revokes the old key and issues a
// new one; Key is shown once, same as Create.
func (s *APIKeysService) Rotate(ctx context.Context, keyID string, opts ...RequestOption) (APIKeyCreated, error) {
	return decode[APIKeyCreated](s.t.do(ctx, "POST", "/v1/api-keys/"+keyID+"/rotate", nil, opts...))
}
