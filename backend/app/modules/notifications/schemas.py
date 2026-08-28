import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    resource_type: str | None
    resource_id: str | None
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountOut(BaseModel):
    unread_count: int
