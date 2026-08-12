import uuid
from datetime import datetime

from pydantic import BaseModel


class PlanOut(BaseModel):
    id: uuid.UUID
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

    model_config = {"from_attributes": True}


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    plan: PlanOut
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    trial_end: datetime | None
    cancel_at_period_end: bool


class InvoiceOut(BaseModel):
    id: uuid.UUID
    stripe_invoice_id: str
    amount_cents: int
    status: str
    invoice_pdf_url: str | None
    period_start: datetime | None
    period_end: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UsageOut(BaseModel):
    period_start: datetime
    period_end: datetime
    delivery_count: int
    max_deliveries_per_month: int | None
    percent_used: float | None
    endpoint_count: int
    max_endpoints: int | None


class CreateCheckoutSessionRequest(BaseModel):
    tier: str  # "starter" | "pro" | "enterprise"
    success_url: str
    cancel_url: str


class CheckoutSessionOut(BaseModel):
    checkout_url: str


class PortalSessionRequest(BaseModel):
    return_url: str


class PortalSessionOut(BaseModel):
    portal_url: str
