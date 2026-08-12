import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.alerts.models import DEFAULT_THROTTLE_WINDOW_MINUTES, AlertChannel, AlertConditionType, AlertSeverity


class CreateAlertRuleRequest(BaseModel):
    condition_type: AlertConditionType
    severity: AlertSeverity = AlertSeverity.WARNING
    channel: AlertChannel
    channel_config: dict = Field(default_factory=dict)
    threshold_config: dict = Field(default_factory=dict)
    throttle_window_minutes: int = Field(default=DEFAULT_THROTTLE_WINDOW_MINUTES, ge=0, le=1440)
    is_enabled: bool = True


class UpdateAlertRuleRequest(BaseModel):
    severity: AlertSeverity | None = None
    channel: AlertChannel | None = None
    channel_config: dict | None = None
    threshold_config: dict | None = None
    throttle_window_minutes: int | None = Field(default=None, ge=0, le=1440)
    is_enabled: bool | None = None


class AlertRuleOut(BaseModel):
    id: uuid.UUID
    condition_type: str
    severity: str
    channel: str
    channel_config: dict
    threshold_config: dict
    throttle_window_minutes: int
    is_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertEventOut(BaseModel):
    id: uuid.UUID
    condition_type: str
    severity: str
    message: str
    resource_id: str | None
    delivery_status: str
    delivery_error: str | None
    triggered_at: datetime
    delivered_at: datetime | None

    model_config = {"from_attributes": True}


class TestAlertResponse(BaseModel):
    delivery_status: str
    delivery_error: str | None
