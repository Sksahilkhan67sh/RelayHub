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
    endpoint_ids: list[uuid.UUID] | None = Field(
        default=None,
        description=(
            "Optional. If omitted (default), the event fans out to every active endpoint in this "
            "environment subscribed to this event type -- the normal webhook behavior. If provided, "
            "delivery is restricted to exactly these endpoint IDs, bypassing each endpoint's normal "
            "subscribed_event_types filter (an explicit selection overrides the subscription filter). "
            "Endpoint IDs that don't belong to this organization, aren't in the given environment, or "
            "aren't active are silently skipped rather than erroring."
        ),
    )

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
