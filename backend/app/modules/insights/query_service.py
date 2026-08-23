"""
Phase 3 -- insights read API's query layer (section 12). Reads the tables written
by workers/insight_tasks.py (EndpointHealthSnapshot, Anomaly, Incident,
RootCauseAnalysis). Every query goes through tenant_select() -- see
db/tenant_query.py's module docstring -- so it's structurally hard to leak
cross-tenant data (section 10's tenant isolation requirement, tested explicitly in
tests/integration/test_insights_api.py's cross-tenant test).

This module does NOT compute anything -- it's a thin, indexed read layer. All the
actual health/anomaly/incident/RCA computation lives in health_analysis.py,
anomaly_detection.py, incident_engine.py, rca.py and runs in the background (see
workers/insight_tasks.py), matching section 19: "do not perform huge
DeliveryAttempt table scans on every dashboard request."
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.tenant_query import tenant_select
from app.modules.insights.models import Anomaly, EndpointHealthSnapshot, Incident, RootCauseAnalysis


async def get_latest_health(db: AsyncSession, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID | None = None) -> list[EndpointHealthSnapshot]:
    """One row per endpoint: its most recent snapshot. Uses a correlated subquery
    on the (endpoint_id, window_end) index created in migration 0016 rather than
    pulling full history and filtering in Python."""

    latest_window_end = (
        select(EndpointHealthSnapshot.endpoint_id, func.max(EndpointHealthSnapshot.window_end).label("max_window_end"))
        .where(EndpointHealthSnapshot.organization_id == organization_id)
        .group_by(EndpointHealthSnapshot.endpoint_id)
    )
    if endpoint_id is not None:
        latest_window_end = latest_window_end.where(EndpointHealthSnapshot.endpoint_id == endpoint_id)
    latest_window_end_subq = latest_window_end.subquery()

    query = select(EndpointHealthSnapshot).join(
        latest_window_end_subq,
        (EndpointHealthSnapshot.endpoint_id == latest_window_end_subq.c.endpoint_id)
        & (EndpointHealthSnapshot.window_end == latest_window_end_subq.c.max_window_end),
    ).where(EndpointHealthSnapshot.organization_id == organization_id)

    return list((await db.execute(query)).scalars().all())


async def get_health_history(
    db: AsyncSession, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID, limit: int = 100, offset: int = 0
) -> list[EndpointHealthSnapshot]:
    query = (
        tenant_select(EndpointHealthSnapshot, organization_id)
        .where(EndpointHealthSnapshot.endpoint_id == endpoint_id)
        .order_by(EndpointHealthSnapshot.window_end.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(query)).scalars().all())


async def list_anomalies(
    db: AsyncSession, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID | None = None, metric: str | None = None,
    since: datetime | None = None, limit: int = 100, offset: int = 0,
) -> list[Anomaly]:
    query = tenant_select(Anomaly, organization_id)
    if endpoint_id is not None:
        query = query.where(Anomaly.endpoint_id == endpoint_id)
    if metric is not None:
        query = query.where(Anomaly.metric == metric)
    if since is not None:
        query = query.where(Anomaly.observed_at >= since)
    query = query.order_by(Anomaly.observed_at.desc()).limit(limit).offset(offset)
    return list((await db.execute(query)).scalars().all())


async def list_incidents(
    db: AsyncSession, *, organization_id: uuid.UUID, status_filter: str | None = None, endpoint_id: uuid.UUID | None = None,
    limit: int = 100, offset: int = 0,
) -> list[Incident]:
    query = tenant_select(Incident, organization_id)
    if status_filter is not None:
        query = query.where(Incident.status == status_filter)
    if endpoint_id is not None:
        query = query.where(Incident.endpoint_id == endpoint_id)
    query = query.order_by(Incident.last_signal_at.desc()).limit(limit).offset(offset)
    return list((await db.execute(query)).scalars().all())


async def get_incident_detail(db: AsyncSession, *, organization_id: uuid.UUID, incident_id: uuid.UUID) -> Incident:
    query = (
        tenant_select(Incident, organization_id)
        .where(Incident.id == incident_id)
        .options(selectinload(Incident.anomalies), selectinload(Incident.rca_entries))
    )
    incident = (await db.execute(query)).scalars().first()
    if incident is None:
        # Tenant-scoped query means "exists but belongs to another org" and
        # "doesn't exist at all" return the identical 404 -- no existence leak
        # across tenants (section 10 / 18.I).
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


async def get_incident_or_404(db: AsyncSession, *, organization_id: uuid.UUID, incident_id: uuid.UUID) -> Incident:
    query = tenant_select(Incident, organization_id).where(Incident.id == incident_id)
    incident = (await db.execute(query)).scalars().first()
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


async def list_rca_for_incident(db: AsyncSession, *, organization_id: uuid.UUID, incident_id: uuid.UUID) -> list[RootCauseAnalysis]:
    await get_incident_or_404(db, organization_id=organization_id, incident_id=incident_id)
    query = (
        tenant_select(RootCauseAnalysis, organization_id)
        .where(RootCauseAnalysis.incident_id == incident_id)
        .order_by(RootCauseAnalysis.created_at.desc())
    )
    return list((await db.execute(query)).scalars().all())


async def get_latest_recommendations(db: AsyncSession, *, organization_id: uuid.UUID, incident_id: uuid.UUID) -> list[str]:
    rca_entries = await list_rca_for_incident(db, organization_id=organization_id, incident_id=incident_id)
    if not rca_entries:
        return []
    # Most recent entry regardless of source (AI entries are added on top of, not
    # instead of, the deterministic one -- see workers/insight_tasks.py).
    return list(rca_entries[0].recommendations)


async def get_incident_timeline(db: AsyncSession, *, organization_id: uuid.UUID, incident_id: uuid.UUID) -> dict:
    """Chronological view: every anomaly folded into this incident, plus the
    incident's own lifecycle timestamps (opened/recovering_since/resolved). The
    frontend renders this as the Incident Timeline section (section 15)."""
    incident = await get_incident_detail(db, organization_id=organization_id, incident_id=incident_id)

    events = [{"type": "incident_opened", "at": incident.opened_at, "detail": incident.title}]
    for a in sorted(incident.anomalies, key=lambda x: x.observed_at):
        events.append(
            {
                "type": "anomaly",
                "at": a.observed_at,
                "detail": f"{a.metric} {a.direction}: {a.observed_value} (baseline {a.baseline_value})",
            }
        )
    if incident.recovering_since:
        events.append({"type": "recovering", "at": incident.recovering_since, "detail": "Stability window started"})
    if incident.resolved_at:
        events.append({"type": "resolved", "at": incident.resolved_at, "detail": "Incident resolved"})

    events.sort(key=lambda e: cast(datetime, e["at"]))
    return {"incident_id": incident.id, "status": incident.status, "events": events}
