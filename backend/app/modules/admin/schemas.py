import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AdminOrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_suspended: bool
    suspension_reason: str | None
    plan_tier: str | None
    subscription_status: str | None
    member_count: int
    endpoint_count: int
    created_at: datetime


class SuspendOrganizationRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class ImpersonationResponse(BaseModel):
    access_token: str
    impersonated_user_email: str
    expires_in: int


class QueueDepthOut(BaseModel):
    queued: int
    processing: int
    retrying: int
    dead_letter: int
    success_last_hour: int
    failed_last_hour: int


class BillingOverviewOut(BaseModel):
    total_organizations: int
    organizations_by_tier: dict[str, int]
    mrr_cents: int
    canceled_this_month: int
    past_due_count: int


class WorkerInstanceOut(BaseModel):
    worker_id: str
    hostname: str
    pid: int
    last_heartbeat_at: datetime
    healthy: bool


class WorkerHealthOut(BaseModel):
    healthy_count: int
    unhealthy_count: int
    workers: list[WorkerInstanceOut]


class DeliveryMetricsOut(BaseModel):
    window_seconds: int
    avg_delivery_latency_ms: float | None
    p95_delivery_latency_ms: int | None
    retry_rate: float | None
    dlq_rate: float | None
    stuck_jobs_count: int
    sample_size: int


class SystemHealthOut(BaseModel):
    database_ok: bool
    queue_depth: QueueDepthOut
    worker_health: WorkerHealthOut
    checked_at: datetime


class CreateFeatureFlagRequest(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    is_enabled_globally: bool = False


class UpdateFeatureFlagRequest(BaseModel):
    description: str | None = Field(default=None, max_length=1000)
    is_enabled_globally: bool | None = None


class FeatureFlagOut(BaseModel):
    id: uuid.UUID
    key: str
    description: str
    is_enabled_globally: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class FeatureFlagOverrideOut(BaseModel):
    id: uuid.UUID
    flag_id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class SetFeatureFlagOverrideRequest(BaseModel):
    organization_id: uuid.UUID
    is_enabled: bool


class CreateAbuseReportRequest(BaseModel):
    organization_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=2000)


class ResolveAbuseReportRequest(BaseModel):
    status: str = Field(pattern="^(investigating|resolved|dismissed)$")
    resolution_notes: str | None = Field(default=None, max_length=2000)


class AbuseReportOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    reason: str
    status: str
    resolution_notes: str | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class ForceActionResponse(BaseModel):
    id: uuid.UUID
    status: str
