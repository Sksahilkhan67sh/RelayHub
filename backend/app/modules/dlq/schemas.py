import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.delivery.schemas import DeliveryAttemptOut


class DeadLetterJobOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str
    payload: dict
    attempt_number: int
    # See DeliveryJobOut.max_attempts. For a DLQ entry this will always equal
    # attempt_number (that equality is what caused the dead-letter in the first
    # place), but exposing it explicitly keeps the DLQ UI from having to assume
    # that invariant rather than just displaying real API data.
    max_attempts: int
    queued_at: datetime
    completed_at: datetime | None
    last_error_category: str | None
    last_error_message: str | None
    attempts: list[DeliveryAttemptOut] = []

    model_config = {"from_attributes": True}


class RetryDeadLetterResponse(BaseModel):
    id: uuid.UUID
    status: str


class BulkRetryRequest(BaseModel):
    job_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class BulkRetryResponse(BaseModel):
    retried: list[uuid.UUID]
    skipped: list[uuid.UUID]
