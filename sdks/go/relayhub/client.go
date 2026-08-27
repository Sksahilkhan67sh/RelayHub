// Package relayhub is the official Go SDK for the RelayHub webhook and event
// delivery API. Every method on every service maps 1:1 to a real REST endpoint
// documented in docs/api -- the SDK adds no business logic of its own.
package relayhub

import (
	"net/http"
	"strings"
	"time"
)

const (
	defaultBaseURL    = "https://api.relayhub.dev/v1"
	defaultTimeout    = 30 * time.Second
	defaultMaxRetries = 2
)

// Client is the entry point to the RelayHub API. Construct with New or NewBuilder.
type Client struct {
	Auth          *AuthService
	APIKeys       *APIKeysService
	Organizations *OrganizationsService
	Endpoints     *EndpointsService
	Events        *EventsService
	Deliveries    *DeliveriesService
	DLQ           *DLQService
	Analytics     *AnalyticsService
	Insights      *InsightsService
	Billing       *BillingService
	Notifications *NotificationsService
	Audit         *AuditService

	transport *transport
}

// Option configures a Client. Use with New, or assemble the same configuration
// fluently with NewBuilder().
type Option func(*clientConfig)

type clientConfig struct {
	baseURL        string
	timeout        time.Duration
	maxRetries     int
	defaultHeaders map[string]string
	httpClient     *http.Client
}

// WithBaseURL overrides the default API base URL (with or without a trailing /v1).
func WithBaseURL(baseURL string) Option {
	return func(c *clientConfig) { c.baseURL = baseURL }
}

// WithClientTimeout sets the default per-request timeout.
func WithClientTimeout(d time.Duration) Option {
	return func(c *clientConfig) { c.timeout = d }
}

// WithClientMaxRetries sets the default retry count for 429/5xx responses and network errors.
func WithClientMaxRetries(n int) Option {
	return func(c *clientConfig) { c.maxRetries = n }
}

// WithDefaultHeader adds a header sent on every request from this client.
func WithDefaultHeader(key, value string) Option {
	return func(c *clientConfig) {
		if c.defaultHeaders == nil {
			c.defaultHeaders = map[string]string{}
		}
		c.defaultHeaders[key] = value
	}
}

// WithHTTPClient swaps the underlying *http.Client (useful for tests or custom transports/proxies).
func WithHTTPClient(httpClient *http.Client) Option {
	return func(c *clientConfig) { c.httpClient = httpClient }
}

// New constructs a Client authenticated with apiKey.
//
//	client := relayhub.New(os.Getenv("RELAYHUB_API_KEY"),
//	    relayhub.WithClientTimeout(10*time.Second),
//	    relayhub.WithClientMaxRetries(3),
//	)
func New(apiKey string, opts ...Option) *Client {
	cfg := &clientConfig{
		baseURL:    defaultBaseURL,
		timeout:    defaultTimeout,
		maxRetries: defaultMaxRetries,
	}
	for _, opt := range opts {
		opt(cfg)
	}
	if cfg.httpClient == nil {
		cfg.httpClient = &http.Client{}
	}

	normalizedBase := strings.TrimSuffix(strings.TrimSuffix(cfg.baseURL, "/"), "/v1")

	t := &transport{
		baseURL:        normalizedBase,
		apiKey:         apiKey,
		timeout:        cfg.timeout,
		maxRetries:     cfg.maxRetries,
		defaultHeaders: cfg.defaultHeaders,
		httpClient:     cfg.httpClient,
	}

	return &Client{
		Auth:          &AuthService{t: t},
		APIKeys:       &APIKeysService{t: t},
		Organizations: newOrganizationsService(t),
		Endpoints:     &EndpointsService{t: t},
		Events:        &EventsService{t: t},
		Deliveries:    &DeliveriesService{t: t},
		DLQ:           &DLQService{t: t},
		Analytics:     &AnalyticsService{t: t},
		Insights:      &InsightsService{t: t},
		Billing:       &BillingService{t: t},
		Notifications: &NotificationsService{t: t},
		Audit:         &AuditService{t: t},
		transport:     t,
	}
}

// Builder is a fluent alternative to New for callers assembling config conditionally.
type Builder struct {
	apiKey string
	opts   []Option
}

// NewBuilder starts a fluent client builder:
//
//	client := relayhub.NewBuilder().
//	    APIKey(os.Getenv("RELAYHUB_API_KEY")).
//	    Timeout(10 * time.Second).
//	    MaxRetries(3).
//	    Header("X-Client-Name", "checkout-service").
//	    Build()
func NewBuilder() *Builder {
	return &Builder{}
}

func (b *Builder) APIKey(apiKey string) *Builder {
	b.apiKey = apiKey
	return b
}

func (b *Builder) BaseURL(baseURL string) *Builder {
	b.opts = append(b.opts, WithBaseURL(baseURL))
	return b
}

func (b *Builder) Timeout(d time.Duration) *Builder {
	b.opts = append(b.opts, WithClientTimeout(d))
	return b
}

func (b *Builder) MaxRetries(n int) *Builder {
	b.opts = append(b.opts, WithClientMaxRetries(n))
	return b
}

func (b *Builder) Header(key, value string) *Builder {
	b.opts = append(b.opts, WithDefaultHeader(key, value))
	return b
}

func (b *Builder) HTTPClient(httpClient *http.Client) *Builder {
	b.opts = append(b.opts, WithHTTPClient(httpClient))
	return b
}

// Build constructs the Client. Panics if APIKey was never set, mirroring the
// other language SDKs' builder.build() behavior (fail fast at construction, not
// on the first call).
func (b *Builder) Build() *Client {
	if b.apiKey == "" {
		panic("relayhub: Builder.APIKey(...) is required before Build()")
	}
	return New(b.apiKey, b.opts...)
}
