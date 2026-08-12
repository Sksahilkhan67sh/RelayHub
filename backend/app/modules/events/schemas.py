import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.endpoints.models import EndpointEnvironment

EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


class PublishEventRequest(BaseModel):
    event: str = Field(min_length=3, max_length=150, description="e.g. 'payment.success' or 'myapp.custom_event'")
    payload: dict = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=255)
    environment: EndpointEnvironment = EndpointEnvironment.TEST

    @field_validator("event")
    @classmethod
    def event_type_format(cls, v: str) -> str:
        if not EVENT_TYPE_PATTERN.match(v):
            raise ValueError(
                "Event type must match '<namespace>.<name>' using lowercase letters, digits, and underscores "
                "(e.g. 'payment.success')"
            )
        return v


class DeliveryJobSummary(BaseModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID
    status: str

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: uuid.UUID
    event: str = Field(validation_alias="event_type")
    environment: str
    payload: dict
    request_id: str
    created_at: datetime
    delivery_jobs: list[DeliveryJobSummary] = Field(default_factory=list)

    model_config = {"from_attributes": True, "populate_by_name": True}
