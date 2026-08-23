"""
Phase 3 -- Insights API (section 12).

IMPORTANT ROUTING NOTE (found during the audit, not assumed away): main.py already
mounts app/modules/analytics/routes.py's router at BOTH /v1/analytics/... and
/v1/insights/... (an ad-blocker-avoidance alias -- see that file's docstring), and
that alias already owns /v1/insights/summary, /endpoint-health, /top-endpoints,
/events-by-type, /deliveries-over-time, /export. Mounting this new AI-intelligence
router at bare /v1/insights/... would collide with (or shadow) that existing,
in-use alias. This router is therefore mounted at /v1/insights/intelligence/... --
still under the "insights" umbrella the brief asks for, with zero risk of colliding
with the existing analytics alias or breaking the ad-blocker workaround it exists
for.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role
from app.modules.insights import query_service
from app.modules.insights.schemas import (
    AnomalyOut,
    EndpointHealthSnapshotOut,
    IncidentDetailOut,
    IncidentOut,
    IncidentTimelineOut,
    RecommendationsOut,
    RootCauseAnalysisOut,
)

router = APIRouter(prefix="/insights/intelligence", tags=["insights-intelligence"])


@router.get("/health", response_model=list[EndpointHealthSnapshotOut])
async def latest_health(
    endpoint_id: uuid.UUID | None = Query(default=None),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    return await query_service.get_latest_health(db, organization_id=auth.organization_id, endpoint_id=endpoint_id)


@router.get("/health/{endpoint_id}/history", response_model=list[EndpointHealthSnapshotOut])
async def health_history(
    endpoint_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    return await query_service.get_health_history(
        db, organization_id=auth.organization_id, endpoint_id=endpoint_id, limit=limit, offset=offset
    )


@router.get("/anomalies", response_model=list[AnomalyOut])
async def anomalies(
    endpoint_id: uuid.UUID | None = Query(default=None),
    metric: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    return await query_service.list_anomalies(
        db, organization_id=auth.organization_id, endpoint_id=endpoint_id, metric=metric, since=since, limit=limit, offset=offset
    )


@router.get("/incidents", response_model=list[IncidentOut])
async def incidents(
    status: str | None = Query(default=None),
    endpoint_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    return await query_service.list_incidents(
        db, organization_id=auth.organization_id, status_filter=status, endpoint_id=endpoint_id, limit=limit, offset=offset
    )


@router.get("/incidents/{incident_id}", response_model=IncidentDetailOut)
async def incident_detail(
    incident_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    return await query_service.get_incident_detail(db, organization_id=auth.organization_id, incident_id=incident_id)


@router.get("/incidents/{incident_id}/rca", response_model=list[RootCauseAnalysisOut])
async def incident_rca(
    incident_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    return await query_service.list_rca_for_incident(db, organization_id=auth.organization_id, incident_id=incident_id)


@router.get("/incidents/{incident_id}/recommendations", response_model=RecommendationsOut)
async def incident_recommendations(
    incident_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    recs = await query_service.get_latest_recommendations(db, organization_id=auth.organization_id, incident_id=incident_id)
    return RecommendationsOut(incident_id=incident_id, recommendations=recs)


@router.get("/incidents/{incident_id}/timeline", response_model=IncidentTimelineOut)
async def incident_timeline(
    incident_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    return await query_service.get_incident_timeline(db, organization_id=auth.organization_id, incident_id=incident_id)
