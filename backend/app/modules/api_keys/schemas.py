import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.api_keys.models import DEFAULT_SCOPES, ApiKeyEnvironment, ApiKeyScope


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    environment: ApiKeyEnvironment = ApiKeyEnvironment.TEST
    scopes: list[str] = Field(default_factory=lambda: list(DEFAULT_SCOPES))
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        valid = {s.value for s in ApiKeyScope}
        invalid = set(v) - valid
        if invalid:
            raise ValueError(f"Invalid scope(s): {sorted(invalid)}. Valid scopes: {sorted(valid)}")
        return v


class ApiKeyCreatedResponse(BaseModel):
    """Returned ONCE at creation time -- the only time the full secret is ever visible."""

    id: uuid.UUID
    name: str
    environment: str
    scopes: list[str]
    key: str  # full secret -- shown once, never retrievable again
    key_prefix: str
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyOut(BaseModel):
    """Safe, masked representation for list/detail views -- never includes the secret."""

    id: uuid.UUID
    name: str
    environment: str
    scopes: list[str]
    key_prefix: str
    masked_key: str
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RevokeApiKeyRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)
