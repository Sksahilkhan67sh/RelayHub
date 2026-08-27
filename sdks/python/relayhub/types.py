"""
Typed response shapes mirroring the real Pydantic schemas in
backend/app/modules/*/schemas.py. These are TypedDicts, not a runtime dependency
like pydantic -- the SDK stays dependency-light (only httpx is required) and every
method still returns something your editor can autocomplete against.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

Role = Literal["owner", "admin", "member", "viewer"]
EndpointEnvironment = Literal["test", "live"]
DeliveryStatus = Literal["queued", "processing", "success", "retrying", "failed", "dead_letter", "pending"]
InvitationStatus = Literal["pending", "accepted", "revoked", "expired"]


class UserOut(TypedDict):
    id: str
    email: str
    full_name: str
    is_platform_admin: bool


class OrganizationOut(TypedDict):
    id: str
    name: str
    slug: str


class MeResponse(TypedDict):
    user: UserOut
    organization: OrganizationOut
    role: Role


class TokenResponse(TypedDict):
    access_token: str
    refresh_token: str
    token_type: str


class MemberOut(TypedDict):
    user_id: str
    email: str
    full_name: str
    role: str
    invited_by_user_id: str | None
    accepted_at: str | None
    joined_at: str


class InvitationOut(TypedDict):
    id: str
    organization_id: str
    email: str
    role: str
    invited_by_user_id: str
    status: InvitationStatus
    expires_at: str
    accepted_at: str | None
    revoked_at: str | None
    created_at: str


class ApiKeyOut(TypedDict):
    id: str
    name: str
    environment: str
    scopes: list[str]
    key_prefix: str
    masked_key: str
    last_used_at: str | None
    expires_at: str | None
    revoked_at: str | None
    is_active: bool
    created_at: str


class ApiKeyCreatedResponse(TypedDict):
    """Only ever returned once, at creation or rotation time -- `key` is never retrievable again."""

    id: str
    name: str
    environment: str
    scopes: list[str]
    key_prefix: str
    key: str
    expires_at: str | None
    created_at: str


class EndpointOut(TypedDict):
    id: str
    name: str
    description: str | None
    url: str
    environment: str
    custom_headers: dict[str, str]
    timeout_seconds: int
    subscribed_event_types: list[str]
    ip_allowlist: list[str]
    is_active: bool
    tls_verification_enabled: bool
    max_retry_attempts: int | None
    health_status: str
    consecutive_failure_count: int
    last_success_at: str | None
    last_failure_at: str | None
    paused_at: str | None
    paused_reason: str | None
    created_at: str


class EndpointSecretOut(TypedDict):
    id: str
    secret: str
    grace_period_ends_at: str | None
    created_at: str


class DeliveryJobSummary(TypedDict):
    id: str
    endpoint_id: str
    status: str


class EventOut(TypedDict):
    id: str
    event: str
    environment: str
    payload: dict[str, Any]
    request_id: str
    created_at: str
    delivery_jobs: list[DeliveryJobSummary]


class DeliveryAttemptOut(TypedDict):
    id: str
    attempt_number: int
    status: str
    response_status_code: int | None
    latency_ms: int | None
    error_category: str | None
    error_message: str | None
    attempted_at: str


class DeliveryJobOut(TypedDict):
    id: str
    event_id: str
    endpoint_id: str
    status: str
    attempt_number: int
    queued_at: str
    next_attempt_at: str | None
    completed_at: str | None
    attempts: list[DeliveryAttemptOut]


class DeliveryLogEntryOut(TypedDict):
    id: str
    event_id: str
    endpoint_id: str
    event_type: str
    environment: str
    request_id: str
    status: str
    attempt_number: int
    queued_at: str
    next_attempt_at: str | None
    completed_at: str | None
    attempts: list[DeliveryAttemptOut]


class DeadLetterJobOut(TypedDict):
    id: str
    event_id: str
    endpoint_id: str
    event_type: str
    payload: dict[str, Any]
    attempt_number: int
    queued_at: str
    completed_at: str | None
    last_error_category: str | None
    last_error_message: str | None
    attempts: list[DeliveryAttemptOut]


class RetryDeadLetterResponse(TypedDict):
    id: str
    status: str


class BulkRetryResponse(TypedDict):
    retried: list[str]
    skipped: list[str]


class SummaryOut(TypedDict):
    total_events: int
    total_deliveries: int
    success_rate: float
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    p99_latency_ms: float | None


class TimeSeriesBucket(TypedDict):
    bucket: str
    success_count: int
    failure_count: int


class EventTypeVolume(TypedDict):
    event_type: str
    count: int


class TopEndpointOut(TypedDict):
    endpoint_id: str
    endpoint_name: str
    delivery_count: int
    failure_rate: float


class EndpointHealthOut(TypedDict):
    endpoint_id: str
    endpoint_name: str
    health_status: str
    consecutive_failure_count: int


class PlanOut(TypedDict):
    id: str
    tier: str
    name: str
    price_cents: int
    max_deliveries_per_month: int | None
    max_endpoints: int | None
    log_retention_days: int
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    rate_limit_per_day: int
    allow_overage: bool
    has_advanced_analytics: bool
    has_priority_support: bool
    has_sso: bool


class SubscriptionOut(TypedDict):
    id: str
    plan: PlanOut
    status: str
    current_period_start: str | None
    current_period_end: str | None
    trial_end: str | None
    cancel_at_period_end: bool


class UsageOut(TypedDict):
    period_start: str
    period_end: str
    delivery_count: int
    max_deliveries_per_month: int | None
    percent_used: float | None
    endpoint_count: int
    max_endpoints: int | None


class InvoiceOut(TypedDict):
    id: str
    stripe_invoice_id: str
    amount_cents: int
    status: str
    invoice_pdf_url: str | None
    period_start: str | None
    period_end: str | None
    created_at: str


class CheckoutSessionOut(TypedDict):
    checkout_url: str


class PortalSessionOut(TypedDict):
    portal_url: str


class AlertRuleOut(TypedDict):
    """"Notifications" in RelayHub's product surface are alert rules -- see NotificationsResource."""

    id: str
    condition_type: str
    severity: str
    channel: str
    channel_config: dict[str, Any]
    threshold_config: dict[str, Any]
    throttle_window_minutes: int
    is_enabled: bool
    created_at: str


class AlertEventOut(TypedDict):
    id: str
    condition_type: str
    severity: str
    message: str
    resource_id: str | None
    delivery_status: str
    delivery_error: str | None
    triggered_at: str
    delivered_at: str | None


class TestAlertResponse(TypedDict):
    delivery_status: str
    delivery_error: str | None


class AuditLogOut(TypedDict):
    id: str
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    metadata: dict[str, Any]
    ip_address: str | None
    created_at: str


class EndpointHealthSnapshotOut(TypedDict):
    """Mirrors backend/app/modules/insights/schemas.py::EndpointHealthSnapshotOut."""

    id: str
    endpoint_id: str
    window_start: str
    window_end: str
    status: str
    health_score: float | None
    confidence: float
    sample_size: int
    success_rate: float | None
    failure_rate: float | None
    http_4xx_rate: float | None
    http_5xx_rate: float | None
    timeout_rate: float | None
    retry_rate: float | None
    dlq_rate: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    supporting_signals: dict[str, Any]


class InsightAnomalyOut(TypedDict):
    id: str
    endpoint_id: str | None
    metric: str
    direction: str
    observed_value: float
    baseline_value: float
    delta: float
    observed_at: str
    confidence: float
    sample_size: int
    evidence: list[Any]
    incident_id: str | None


class RootCauseAnalysisOut(TypedDict):
    id: str
    source: str  # "deterministic" | "ai" -- keep this distinction visible wherever you render it
    likely_cause: str
    confidence_level: str
    confidence_score: float
    evidence: list[Any]
    recommendations: list[str]
    ai_provider: str | None
    ai_model: str | None
    created_at: str


class IncidentOut(TypedDict):
    id: str
    endpoint_id: str | None
    status: str
    failure_category: str
    severity: str
    title: str
    summary: str
    opened_at: str
    recovering_since: str | None
    resolved_at: str | None
    last_signal_at: str


class IncidentDetailOut(IncidentOut):
    anomalies: list[InsightAnomalyOut]
    rca_entries: list[RootCauseAnalysisOut]


class RecommendationsOut(TypedDict):
    incident_id: str
    recommendations: list[str]


class IncidentTimelineEventOut(TypedDict):
    type: str
    at: str
    detail: str


class IncidentTimelineOut(TypedDict):
    incident_id: str
    status: str
    events: list[IncidentTimelineEventOut]
