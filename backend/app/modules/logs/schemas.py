import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.delivery.schemas import DeliveryAttemptOut


class DeliveryLogEntryOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str
    environment: str
    request_id: str
    status: str
    attempt_number: int
    queued_at: datetime
    next_attempt_at: datetime | None
    completed_at: datetime | None
    attempts: list[DeliveryAttemptOut] = []

    model_config = {"from_attributes": True}
