import uuid
from datetime import datetime

from pydantic import BaseModel


class DeliveryAttemptOut(BaseModel):
    id: uuid.UUID
    attempt_number: int
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    http_status: int | None
    response_headers: dict = {}
    response_body_truncated: str | None = None
    error_category: str
    error_message: str | None
    worker_id: str
    destination_ip: str | None

    model_config = {"from_attributes": True}


class DeliveryJobOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str
    payload: dict
    status: str
    attempt_number: int
    queued_at: datetime
    next_attempt_at: datetime | None
    completed_at: datetime | None
    attempts: list[DeliveryAttemptOut] = []

    model_config = {"from_attributes": True}
