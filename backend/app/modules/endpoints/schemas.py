import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.endpoints.models import EndpointEnvironment
from app.modules.endpoints.security import UnsafeEndpointURLError, validate_endpoint_url_at_registration


class CreateEndpointRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    url: str = Field(min_length=1, max_length=2048)
    environment: EndpointEnvironment = EndpointEnvironment.TEST
    custom_headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=15, ge=1, le=120)
    subscribed_event_types: list[str] = Field(default_factory=list)
    ip_allowlist: list[str] = Field(default_factory=list)
    tls_verification_enabled: bool = True
    max_retry_attempts: int | None = Field(default=None, ge=0, le=20)

    @field_validator("url")
    @classmethod
    def url_must_be_safe(cls, v: str) -> str:
        try:
            validate_endpoint_url_at_registration(v)
        except UnsafeEndpointURLError as e:
            raise ValueError(str(e)) from e
        return v


class UpdateEndpointRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    custom_headers: dict[str, str] | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=120)
    subscribed_event_types: list[str] | None = None
    ip_allowlist: list[str] | None = None
    is_active: bool | None = None
    tls_verification_enabled: bool | None = None
    max_retry_attempts: int | None = Field(default=None, ge=0, le=20)

    @field_validator("url")
    @classmethod
    def url_must_be_safe(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            validate_endpoint_url_at_registration(v)
        except UnsafeEndpointURLError as e:
            raise ValueError(str(e)) from e
        return v


class EndpointOut(BaseModel):
    id: uuid.UUID
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
    last_success_at: datetime | None
    last_failure_at: datetime | None
    paused_at: datetime | None
    paused_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RotateSecretRequest(BaseModel):
    grace_period_hours: int = Field(default=24, ge=0, le=720)


class EndpointSecretOut(BaseModel):
    """Secret is shown once at creation/rotation time; never again after."""

    id: uuid.UUID
    secret: str
    grace_period_ends_at: datetime | None
    created_at: datetime
