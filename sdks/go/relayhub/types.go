package relayhub

// Typed models mirroring the real Pydantic response schemas in
// backend/app/modules/*/schemas.py. Field names/JSON tags match the API's actual
// JSON exactly -- see docs/api for the endpoint each one corresponds to.

type User struct {
	ID              string `json:"id"`
	Email           string `json:"email"`
	FullName        string `json:"full_name"`
	IsPlatformAdmin bool   `json:"is_platform_admin"`
}

type Organization struct {
	ID   string `json:"id"`
	Name string `json:"name"`
	Slug string `json:"slug"`
}

type MeResponse struct {
	User         User         `json:"user"`
	Organization Organization `json:"organization"`
	Role         string       `json:"role"`
}

type TokenResponse struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	TokenType    string `json:"token_type"`
}

type Member struct {
	UserID        string  `json:"user_id"`
	Email         string  `json:"email"`
	FullName      string  `json:"full_name"`
	Role          string  `json:"role"`
	InvitedByUser *string `json:"invited_by_user_id"`
	AcceptedAt    *string `json:"accepted_at"`
	JoinedAt      string  `json:"joined_at"`
}

type Invitation struct {
	ID              string  `json:"id"`
	OrganizationID  string  `json:"organization_id"`
	Email           string  `json:"email"`
	Role            string  `json:"role"`
	InvitedByUserID string  `json:"invited_by_user_id"`
	Status          string  `json:"status"`
	ExpiresAt       string  `json:"expires_at"`
	AcceptedAt      *string `json:"accepted_at"`
	RevokedAt       *string `json:"revoked_at"`
	CreatedAt       string  `json:"created_at"`
}

type APIKey struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Environment string   `json:"environment"`
	Scopes      []string `json:"scopes"`
	KeyPrefix   string   `json:"key_prefix"`
	MaskedKey   string   `json:"masked_key"`
	LastUsedAt  *string  `json:"last_used_at"`
	ExpiresAt   *string  `json:"expires_at"`
	RevokedAt   *string  `json:"revoked_at"`
	IsActive    bool     `json:"is_active"`
	CreatedAt   string   `json:"created_at"`
}

// APIKeyCreated is only ever returned once, at creation or rotation time -- Key is never retrievable again.
type APIKeyCreated struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Environment string   `json:"environment"`
	Scopes      []string `json:"scopes"`
	KeyPrefix   string   `json:"key_prefix"`
	Key         string   `json:"key"`
	ExpiresAt   *string  `json:"expires_at"`
	CreatedAt   string   `json:"created_at"`
}

type Endpoint struct {
	ID                      string            `json:"id"`
	Name                    string            `json:"name"`
	Description             *string           `json:"description"`
	URL                     string            `json:"url"`
	Environment             string            `json:"environment"`
	CustomHeaders           map[string]string `json:"custom_headers"`
	TimeoutSeconds          int               `json:"timeout_seconds"`
	SubscribedEventTypes    []string          `json:"subscribed_event_types"`
	IPAllowlist             []string          `json:"ip_allowlist"`
	IsActive                bool              `json:"is_active"`
	TLSVerificationEnabled  bool              `json:"tls_verification_enabled"`
	MaxRetryAttempts        *int              `json:"max_retry_attempts"`
	HealthStatus            string            `json:"health_status"`
	ConsecutiveFailureCount int               `json:"consecutive_failure_count"`
	LastSuccessAt           *string           `json:"last_success_at"`
	LastFailureAt           *string           `json:"last_failure_at"`
	PausedAt                *string           `json:"paused_at"`
	PausedReason            *string           `json:"paused_reason"`
	CreatedAt               string            `json:"created_at"`
}

type EndpointSecret struct {
	ID                string  `json:"id"`
	Secret            string  `json:"secret"`
	GracePeriodEndsAt *string `json:"grace_period_ends_at"`
	CreatedAt         string  `json:"created_at"`
}

type DeliveryJobSummary struct {
	ID         string `json:"id"`
	EndpointID string `json:"endpoint_id"`
	Status     string `json:"status"`
}

type Event struct {
	ID           string               `json:"id"`
	EventType    string               `json:"event"`
	Environment  string               `json:"environment"`
	Payload      map[string]any       `json:"payload"`
	RequestID    string               `json:"request_id"`
	CreatedAt    string               `json:"created_at"`
	DeliveryJobs []DeliveryJobSummary `json:"delivery_jobs"`
}

type DeliveryAttempt struct {
	ID                 string  `json:"id"`
	AttemptNumber      int     `json:"attempt_number"`
	Status             string  `json:"status"`
	ResponseStatusCode *int    `json:"response_status_code"`
	LatencyMs          *int    `json:"latency_ms"`
	ErrorCategory      *string `json:"error_category"`
	ErrorMessage       *string `json:"error_message"`
	AttemptedAt        string  `json:"attempted_at"`
}

type DeliveryJob struct {
	ID            string            `json:"id"`
	EventID       string            `json:"event_id"`
	EndpointID    string            `json:"endpoint_id"`
	Status        string            `json:"status"`
	AttemptNumber int               `json:"attempt_number"`
	QueuedAt      string            `json:"queued_at"`
	NextAttemptAt *string           `json:"next_attempt_at"`
	CompletedAt   *string           `json:"completed_at"`
	Attempts      []DeliveryAttempt `json:"attempts"`
}

type DeliveryLogEntry struct {
	ID            string            `json:"id"`
	EventID       string            `json:"event_id"`
	EndpointID    string            `json:"endpoint_id"`
	EventType     string            `json:"event_type"`
	Environment   string            `json:"environment"`
	RequestID     string            `json:"request_id"`
	Status        string            `json:"status"`
	AttemptNumber int               `json:"attempt_number"`
	QueuedAt      string            `json:"queued_at"`
	NextAttemptAt *string           `json:"next_attempt_at"`
	CompletedAt   *string           `json:"completed_at"`
	Attempts      []DeliveryAttempt `json:"attempts"`
}

type DeadLetterJob struct {
	ID                string            `json:"id"`
	EventID           string            `json:"event_id"`
	EndpointID        string            `json:"endpoint_id"`
	EventType         string            `json:"event_type"`
	Payload           map[string]any    `json:"payload"`
	AttemptNumber     int               `json:"attempt_number"`
	QueuedAt          string            `json:"queued_at"`
	CompletedAt       *string           `json:"completed_at"`
	LastErrorCategory *string           `json:"last_error_category"`
	LastErrorMessage  *string           `json:"last_error_message"`
	Attempts          []DeliveryAttempt `json:"attempts"`
}

type RetryDeadLetterResponse struct {
	ID     string `json:"id"`
	Status string `json:"status"`
}

type BulkRetryResponse struct {
	Retried []string `json:"retried"`
	Skipped []string `json:"skipped"`
}

type Summary struct {
	TotalEvents     int      `json:"total_events"`
	TotalDeliveries int      `json:"total_deliveries"`
	SuccessRate     float64  `json:"success_rate"`
	P50LatencyMs    *float64 `json:"p50_latency_ms"`
	P95LatencyMs    *float64 `json:"p95_latency_ms"`
	P99LatencyMs    *float64 `json:"p99_latency_ms"`
}

type TimeSeriesBucket struct {
	Bucket       string `json:"bucket"`
	SuccessCount int    `json:"success_count"`
	FailureCount int    `json:"failure_count"`
}

type EventTypeVolume struct {
	EventType string `json:"event_type"`
	Count     int    `json:"count"`
}

type TopEndpoint struct {
	EndpointID    string  `json:"endpoint_id"`
	EndpointName  string  `json:"endpoint_name"`
	DeliveryCount int     `json:"delivery_count"`
	FailureRate   float64 `json:"failure_rate"`
}

type EndpointHealth struct {
	EndpointID              string `json:"endpoint_id"`
	EndpointName            string `json:"endpoint_name"`
	HealthStatus            string `json:"health_status"`
	ConsecutiveFailureCount int    `json:"consecutive_failure_count"`
}

type Plan struct {
	ID                    string `json:"id"`
	Tier                  string `json:"tier"`
	Name                  string `json:"name"`
	PriceCents            int    `json:"price_cents"`
	MaxDeliveriesPerMonth *int   `json:"max_deliveries_per_month"`
	MaxEndpoints          *int   `json:"max_endpoints"`
	LogRetentionDays      int    `json:"log_retention_days"`
	RateLimitPerMinute    int    `json:"rate_limit_per_minute"`
	RateLimitPerHour      int    `json:"rate_limit_per_hour"`
	RateLimitPerDay       int    `json:"rate_limit_per_day"`
	AllowOverage          bool   `json:"allow_overage"`
	HasAdvancedAnalytics  bool   `json:"has_advanced_analytics"`
	HasPrioritySupport    bool   `json:"has_priority_support"`
	HasSSO                bool   `json:"has_sso"`
}

type Subscription struct {
	ID                 string  `json:"id"`
	Plan               Plan    `json:"plan"`
	Status             string  `json:"status"`
	CurrentPeriodStart *string `json:"current_period_start"`
	CurrentPeriodEnd   *string `json:"current_period_end"`
	TrialEnd           *string `json:"trial_end"`
	CancelAtPeriodEnd  bool    `json:"cancel_at_period_end"`
}

type Usage struct {
	PeriodStart           string   `json:"period_start"`
	PeriodEnd             string   `json:"period_end"`
	DeliveryCount         int      `json:"delivery_count"`
	MaxDeliveriesPerMonth *int     `json:"max_deliveries_per_month"`
	PercentUsed           *float64 `json:"percent_used"`
	EndpointCount         int      `json:"endpoint_count"`
	MaxEndpoints          *int     `json:"max_endpoints"`
}

type Invoice struct {
	ID              string  `json:"id"`
	StripeInvoiceID string  `json:"stripe_invoice_id"`
	AmountCents     int     `json:"amount_cents"`
	Status          string  `json:"status"`
	InvoicePDFURL   *string `json:"invoice_pdf_url"`
	PeriodStart     *string `json:"period_start"`
	PeriodEnd       *string `json:"period_end"`
	CreatedAt       string  `json:"created_at"`
}

type CheckoutSession struct {
	CheckoutURL string `json:"checkout_url"`
}

type PortalSession struct {
	PortalURL string `json:"portal_url"`
}

// AlertRule -- "notifications" in RelayHub's product surface are alert rules; see NotificationsService.
type AlertRule struct {
	ID                    string         `json:"id"`
	ConditionType         string         `json:"condition_type"`
	Severity              string         `json:"severity"`
	Channel               string         `json:"channel"`
	ChannelConfig         map[string]any `json:"channel_config"`
	ThresholdConfig       map[string]any `json:"threshold_config"`
	ThrottleWindowMinutes int            `json:"throttle_window_minutes"`
	IsEnabled             bool           `json:"is_enabled"`
	CreatedAt             string         `json:"created_at"`
}

type AlertEvent struct {
	ID             string  `json:"id"`
	ConditionType  string  `json:"condition_type"`
	Severity       string  `json:"severity"`
	Message        string  `json:"message"`
	ResourceID     *string `json:"resource_id"`
	DeliveryStatus string  `json:"delivery_status"`
	DeliveryError  *string `json:"delivery_error"`
	TriggeredAt    string  `json:"triggered_at"`
	DeliveredAt    *string `json:"delivered_at"`
}

type TestAlertResponse struct {
	DeliveryStatus string  `json:"delivery_status"`
	DeliveryError  *string `json:"delivery_error"`
}

type AuditLog struct {
	ID           string         `json:"id"`
	ActorUserID  *string        `json:"actor_user_id"`
	Action       string         `json:"action"`
	ResourceType string         `json:"resource_type"`
	ResourceID   *string        `json:"resource_id"`
	Metadata     map[string]any `json:"metadata"`
	IPAddress    *string        `json:"ip_address"`
	CreatedAt    string         `json:"created_at"`
}

// EndpointHealthSnapshot mirrors backend/app/modules/insights/schemas.py::EndpointHealthSnapshotOut.
type EndpointHealthSnapshot struct {
	ID                string         `json:"id"`
	EndpointID        string         `json:"endpoint_id"`
	WindowStart       string         `json:"window_start"`
	WindowEnd         string         `json:"window_end"`
	Status            string         `json:"status"`
	HealthScore       *float64       `json:"health_score"`
	Confidence        float64        `json:"confidence"`
	SampleSize        int            `json:"sample_size"`
	SuccessRate       *float64       `json:"success_rate"`
	FailureRate       *float64       `json:"failure_rate"`
	Http4xxRate       *float64       `json:"http_4xx_rate"`
	Http5xxRate       *float64       `json:"http_5xx_rate"`
	TimeoutRate       *float64       `json:"timeout_rate"`
	RetryRate         *float64       `json:"retry_rate"`
	DlqRate           *float64       `json:"dlq_rate"`
	LatencyP50Ms      *float64       `json:"latency_p50_ms"`
	LatencyP95Ms      *float64       `json:"latency_p95_ms"`
	SupportingSignals map[string]any `json:"supporting_signals"`
}

type InsightAnomaly struct {
	ID            string  `json:"id"`
	EndpointID    *string `json:"endpoint_id"`
	Metric        string  `json:"metric"`
	Direction     string  `json:"direction"`
	ObservedValue float64 `json:"observed_value"`
	BaselineValue float64 `json:"baseline_value"`
	Delta         float64 `json:"delta"`
	ObservedAt    string  `json:"observed_at"`
	Confidence    float64 `json:"confidence"`
	SampleSize    int     `json:"sample_size"`
	Evidence      []any   `json:"evidence"`
	IncidentID    *string `json:"incident_id"`
}

// RootCauseAnalysis -- Source is "deterministic" or "ai"; keep this
// distinction visible in anything built on top of this type.
type RootCauseAnalysis struct {
	ID              string   `json:"id"`
	Source          string   `json:"source"`
	LikelyCause     string   `json:"likely_cause"`
	ConfidenceLevel string   `json:"confidence_level"`
	ConfidenceScore float64  `json:"confidence_score"`
	Evidence        []any    `json:"evidence"`
	Recommendations []string `json:"recommendations"`
	AIProvider      *string  `json:"ai_provider"`
	AIModel         *string  `json:"ai_model"`
	CreatedAt       string   `json:"created_at"`
}

type Incident struct {
	ID              string  `json:"id"`
	EndpointID      *string `json:"endpoint_id"`
	Status          string  `json:"status"`
	FailureCategory string  `json:"failure_category"`
	Severity        string  `json:"severity"`
	Title           string  `json:"title"`
	Summary         string  `json:"summary"`
	OpenedAt        string  `json:"opened_at"`
	RecoveringSince *string `json:"recovering_since"`
	ResolvedAt      *string `json:"resolved_at"`
	LastSignalAt    string  `json:"last_signal_at"`
}

type IncidentDetail struct {
	Incident
	Anomalies  []InsightAnomaly    `json:"anomalies"`
	RCAEntries []RootCauseAnalysis `json:"rca_entries"`
}

type Recommendations struct {
	IncidentID      string   `json:"incident_id"`
	Recommendations []string `json:"recommendations"`
}

type IncidentTimelineEvent struct {
	Type   string `json:"type"`
	At     string `json:"at"`
	Detail string `json:"detail"`
}

type IncidentTimeline struct {
	IncidentID string                  `json:"incident_id"`
	Status     string                  `json:"status"`
	Events     []IncidentTimelineEvent `json:"events"`
}
