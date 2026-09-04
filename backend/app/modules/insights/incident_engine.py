"""
Phase 3 -- incident engine (section 5). Converts related anomalies into incidents
rather than creating one per failed delivery or even one per anomaly. Correlation
key is (endpoint_id, "is there already a non-terminal incident open"), matching
the brief's "correlate using endpoint, time window, failure type" -- an endpoint
already under investigation absorbs new anomalies into the SAME incident instead of
spawning duplicates (section 18.L: "duplicate incident/anomaly prevention").

Recovery uses a stability window (section 5): an OPEN/INVESTIGATING incident moves
to RECOVERING the first time a window comes back healthy, then to RESOLVED only
after INSIGHTS_INCIDENT_STABILITY_WINDOWS consecutive healthy windows -- one good
window right after a spike is not proof it's over.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.insights.aggregation import WindowMetrics
from app.modules.insights.failure_classification import classify_failure
from app.modules.insights.models import Anomaly, HealthStatus, Incident, IncidentStatus

_NON_TERMINAL_STATUSES = (IncidentStatus.OPEN.value, IncidentStatus.INVESTIGATING.value, IncidentStatus.RECOVERING.value)

_SEVERITY_BY_CONFIDENCE = [
    (0.85, "critical"),
    (0.6, "warning"),
    (0.0, "info"),
]


def _severity_for(max_confidence: float) -> str:
    for threshold, severity in _SEVERITY_BY_CONFIDENCE:
        if max_confidence >= threshold:
            return severity
    return "info"


async def _find_open_incident(db: AsyncSession, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID | None) -> Incident | None:
    query = select(Incident).where(
        Incident.organization_id == organization_id,
        Incident.endpoint_id == endpoint_id,
        Incident.status.in_(_NON_TERMINAL_STATUSES),
    )
    return (await db.execute(query)).scalars().first()


def _build_title_and_summary(failure_category: str, anomaly_dicts: list[dict], metrics: WindowMetrics) -> tuple[str, str]:
    metric_labels = sorted({a["metric"].replace("_", " ") for a in anomaly_dicts})
    title = f"{failure_category.replace('_', ' ').title()} -- {', '.join(metric_labels)}"

    facts = []
    if metrics.failure_rate is not None:
        facts.append(f"failure rate {metrics.failure_rate:.0%}")
    if metrics.http_5xx_rate:
        facts.append(f"HTTP 5xx rate {metrics.http_5xx_rate:.0%}")
    if metrics.latency_p95_ms is not None:
        facts.append(f"p95 latency {metrics.latency_p95_ms:.0f}ms")
    summary = f"Detected across {metrics.sample_size} delivery attempts: " + ", ".join(facts) if facts else \
        f"Anomalous behaviour detected across {metrics.sample_size} delivery attempts."

    return title, summary


async def correlate_anomalies(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    endpoint_id: uuid.UUID | None,
    anomaly_dicts: list[dict],
    metrics: WindowMetrics,
    observed_at: datetime,
) -> tuple[Incident | None, list[Anomaly]]:
    """Persists the given anomaly dicts as Anomaly rows, and folds them into an
    incident if (a) there's already a non-terminal incident for this endpoint, or
    (b) the anomaly evidence is strong enough to open a new one. Returns
    (incident_or_None, persisted_anomaly_rows). Anomalies below the incident
    threshold are still persisted (visible in the anomaly feed) but stay
    unattached -- not every anomaly is incident-worthy (section 5)."""

    persisted: list[Anomaly] = []
    for a in anomaly_dicts:
        row = Anomaly(**a)
        db.add(row)
        persisted.append(row)

    if not anomaly_dicts:
        return None, persisted

    # Only anomalies with reasonable confidence escalate to incident level --
    # avoids opening an incident off a single borderline signal. A "drop" in a
    # rate metric (failure/retry/dlq/timeout rate going DOWN) is an improvement,
    # not a problem -- it must never open a new incident or knock an existing one
    # out of RECOVERING back into INVESTIGATING, so it's excluded from escalation
    # entirely. (status_distribution anomalies are always direction="regression",
    # so they're unaffected by this filter.)
    escalating = [a for a in anomaly_dicts if a["confidence"] >= 0.5 and a["direction"] != "drop"]
    if not escalating:
        return None, persisted

    failure_category, _proportion = classify_failure(metrics)
    max_confidence = max(a["confidence"] for a in escalating)

    existing = await _find_open_incident(db, organization_id=organization_id, endpoint_id=endpoint_id)
    if existing:
        existing.last_signal_at = observed_at
        existing.failure_category = failure_category
        existing.severity = _severity_for(max(max_confidence, _confidence_of(existing.severity)))
        # An incident that was drifting toward RECOVERING but sees fresh anomalies
        # goes back to INVESTIGATING -- the stability window resets.
        if existing.status == IncidentStatus.RECOVERING.value:
            existing.status = IncidentStatus.INVESTIGATING.value
            existing.recovering_since = None
        for row in persisted:
            row.incident_id = existing.id
        return existing, persisted

    title, summary = _build_title_and_summary(failure_category, escalating, metrics)
    incident = Incident(
        organization_id=organization_id,
        endpoint_id=endpoint_id,
        status=IncidentStatus.OPEN.value,
        failure_category=failure_category,
        severity=_severity_for(max_confidence),
        title=title,
        summary=summary,
        opened_at=observed_at,
        last_signal_at=observed_at,
    )
    db.add(incident)
    await db.flush()  # need incident.id to attach anomalies
    for row in persisted:
        row.incident_id = incident.id

    return incident, persisted


def _confidence_of(severity: str) -> float:
    # Inverse of _severity_for, used only to avoid downgrading severity when a new,
    # weaker anomaly arrives on top of an already-critical incident.
    return {"critical": 0.85, "warning": 0.6, "info": 0.0}.get(severity, 0.0)


async def evaluate_incident_recovery(
    db: AsyncSession, *, incident: Incident, current_health_status: str, observed_at: datetime
) -> None:
    """Called once per window for every non-terminal incident's endpoint (see
    workers/insight_tasks.py), independent of whether new anomalies fired this
    window. A healthy window nudges the incident toward RESOLVED; a non-healthy one
    resets the stability counter."""

    if incident.status not in _NON_TERMINAL_STATUSES:
        return

    is_healthy_window = current_health_status in (HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value)

    if not is_healthy_window:
        if incident.status == IncidentStatus.RECOVERING.value:
            incident.status = IncidentStatus.INVESTIGATING.value
            incident.recovering_since = None
        return

    if incident.status in (IncidentStatus.OPEN.value, IncidentStatus.INVESTIGATING.value):
        incident.status = IncidentStatus.RECOVERING.value
        incident.recovering_since = observed_at
        return

    if incident.status == IncidentStatus.RECOVERING.value and incident.recovering_since is not None:
        # Count how many stability windows have elapsed. workers/insight_tasks.py
        # runs this once per INSIGHTS_HEALTH_WINDOW_MINUTES, so elapsed windows is
        # just elapsed wall-clock time divided by the window size.
        elapsed_minutes = (observed_at - incident.recovering_since).total_seconds() / 60
        required_minutes = settings.INSIGHTS_HEALTH_WINDOW_MINUTES * settings.INSIGHTS_INCIDENT_STABILITY_WINDOWS
        if elapsed_minutes >= required_minutes:
            incident.status = IncidentStatus.RESOLVED.value
            incident.resolved_at = observed_at
