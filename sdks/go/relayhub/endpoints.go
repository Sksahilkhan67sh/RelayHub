package relayhub

import "context"

type EndpointsService struct{ t *transport }

type CreateEndpointRequest struct {
	Name                   string            `json:"name"`
	URL                    string            `json:"url"`
	Description            string            `json:"description,omitempty"`
	Environment            string            `json:"environment,omitempty"`
	CustomHeaders          map[string]string `json:"custom_headers,omitempty"`
	TimeoutSeconds         int               `json:"timeout_seconds,omitempty"`
	SubscribedEventTypes   []string          `json:"subscribed_event_types,omitempty"`
	IPAllowlist            []string          `json:"ip_allowlist,omitempty"`
	TLSVerificationEnabled *bool             `json:"tls_verification_enabled,omitempty"`
	MaxRetryAttempts       *int              `json:"max_retry_attempts,omitempty"`
}

// UpdateEndpointRequest fields are all optional -- only set ones are sent, since
// each field is a pointer/omitempty and this struct is marshaled as-is.
type UpdateEndpointRequest struct {
	Name                   *string           `json:"name,omitempty"`
	URL                    *string           `json:"url,omitempty"`
	Description            *string           `json:"description,omitempty"`
	CustomHeaders          map[string]string `json:"custom_headers,omitempty"`
	TimeoutSeconds         *int              `json:"timeout_seconds,omitempty"`
	SubscribedEventTypes   []string          `json:"subscribed_event_types,omitempty"`
	IPAllowlist            []string          `json:"ip_allowlist,omitempty"`
	TLSVerificationEnabled *bool             `json:"tls_verification_enabled,omitempty"`
	MaxRetryAttempts       *int              `json:"max_retry_attempts,omitempty"`
	IsActive               *bool             `json:"is_active,omitempty"`
}

// Create calls POST /v1/endpoints.
func (s *EndpointsService) Create(ctx context.Context, req CreateEndpointRequest, opts ...RequestOption) (Endpoint, error) {
	return decode[Endpoint](s.t.do(ctx, "POST", "/v1/endpoints", req, opts...))
}

// List calls GET /v1/endpoints.
func (s *EndpointsService) List(ctx context.Context, opts ...RequestOption) ([]Endpoint, error) {
	return decode[[]Endpoint](s.t.do(ctx, "GET", "/v1/endpoints", nil, opts...))
}

// Get calls GET /v1/endpoints/{id}.
func (s *EndpointsService) Get(ctx context.Context, endpointID string, opts ...RequestOption) (Endpoint, error) {
	return decode[Endpoint](s.t.do(ctx, "GET", "/v1/endpoints/"+endpointID, nil, opts...))
}

// Update calls PATCH /v1/endpoints/{id}.
func (s *EndpointsService) Update(ctx context.Context, endpointID string, req UpdateEndpointRequest, opts ...RequestOption) (Endpoint, error) {
	return decode[Endpoint](s.t.do(ctx, "PATCH", "/v1/endpoints/"+endpointID, req, opts...))
}

// Delete calls DELETE /v1/endpoints/{id} (204 No Content on success).
func (s *EndpointsService) Delete(ctx context.Context, endpointID string, opts ...RequestOption) error {
	_, err := s.t.do(ctx, "DELETE", "/v1/endpoints/"+endpointID, nil, opts...)
	return err
}

// RotateSecret calls POST /v1/endpoints/{id}/rotate-secret. The new secret is
// returned once, here. gracePeriodHours keeps the old secret valid in parallel
// so in-flight verification on the receiving end doesn't break mid-rotation.
func (s *EndpointsService) RotateSecret(ctx context.Context, endpointID string, gracePeriodHours int, opts ...RequestOption) (EndpointSecret, error) {
	body := map[string]int{"grace_period_hours": gracePeriodHours}
	return decode[EndpointSecret](s.t.do(ctx, "POST", "/v1/endpoints/"+endpointID+"/rotate-secret", body, opts...))
}
