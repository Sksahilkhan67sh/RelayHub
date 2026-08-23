import uuid
from datetime import datetime

from pydantic import BaseModel


class EndpointHealthSnapshotOut(BaseModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID
    window_start: datetime
    window_end: datetime
    status: str
    health_score: float | None
    confidence: float
    sample_size: int
    success_rate: float | None
    failure_rate: float | None
    http_4xx_rate: float | None
    http_5xx_rate: float | None
    timeout_rate: float | None
    retry_rate: float | None
    dlq_rate: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    supporting_signals: dict

    model_config = {"from_attributes": True}


class AnomalyOut(BaseModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID | None
    metric: str
    direction: str
    observed_value: float
    baseline_value: float
    delta: float
    observed_at: datetime
    confidence: float
    sample_size: int
    evidence: list
    incident_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class RootCauseAnalysisOut(BaseModel):
    id: uuid.UUID
    source: str  # "deterministic" | "ai" -- frontend uses this for the FACT vs AI INFERENCE split
    likely_cause: str
    confidence_level: str
    confidence_score: float
    evidence: list
    recommendations: list
    ai_provider: str | None
    ai_model: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentOut(BaseModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID | None
    status: str
    failure_category: str
    severity: str
    title: str
    summary: str
    opened_at: datetime
    recovering_since: datetime | None
    resolved_at: datetime | None
    last_signal_at: datetime

    model_config = {"from_attributes": True}


class IncidentDetailOut(IncidentOut):
    anomalies: list[AnomalyOut]
    rca_entries: list[RootCauseAnalysisOut]


class RecommendationsOut(BaseModel):
    incident_id: uuid.UUID
    recommendations: list[str]


class TimelineEventOut(BaseModel):
    type: str
    at: datetime
    detail: str


class IncidentTimelineOut(BaseModel):
    incident_id: uuid.UUID
    status: str
    events: list[TimelineEventOut]
