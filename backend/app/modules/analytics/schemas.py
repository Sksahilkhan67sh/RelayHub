import uuid
from datetime import datetime

from pydantic import BaseModel


class SummaryOut(BaseModel):
    total_events: int
    total_deliveries: int
    success_count: int
    failed_count: int
    retrying_count: int
    dead_letter_count: int
    success_rate: float | None
    failure_rate: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    latency_p99_ms: float | None


class TimeSeriesBucket(BaseModel):
    bucket: str  # ISO-ish bucket label, e.g. "2026-07-07 14:00:00"
    total_count: int
    success_count: int
    failed_count: int


class EventTypeVolume(BaseModel):
    event_type: str
    count: int


class TopEndpointOut(BaseModel):
    endpoint_id: uuid.UUID
    name: str
    delivery_count: int
    success_count: int
    success_rate: float | None
    avg_latency_ms: float | None


class EndpointHealthOut(BaseModel):
    endpoint_id: uuid.UUID
    name: str
    health_status: str
    consecutive_failure_count: int
    last_success_at: datetime | None
    last_failure_at: datetime | None
    is_active: bool
