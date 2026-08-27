"""
Phase 5B -- assembles the tenant-scoped context the copilot is allowed to see.

Deliberately reuses app/modules/insights/query_service.py rather than writing new
queries: every function called here already goes through tenant_select() (see that
module's docstring), so this file cannot leak cross-tenant data by construction --
it has no query of its own to get wrong.

Scope is intentionally narrow: recent open/investigating incidents (with their
latest RCA) and current endpoint health. Same "aggregated, not raw" boundary the
existing incident-analysis prompt (ai/prompt.py) already enforces -- this module
never touches DeliveryAttempt rows, endpoint secrets, API keys, or other orgs'
data.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.insights import query_service
from app.modules.insights.models import EndpointHealthSnapshot, Incident, RootCauseAnalysis

_MAX_INCIDENTS_IN_CONTEXT = 8


@dataclass
class CopilotIncidentContext:
    incident_id: uuid.UUID
    title: str
    status: str
    severity: str
    failure_category: str
    summary: str
    latest_rca: RootCauseAnalysis | None


@dataclass
class CopilotContext:
    incidents: list[CopilotIncidentContext] = field(default_factory=list)
    health_snapshots: list[EndpointHealthSnapshot] = field(default_factory=list)
    focused_incident: CopilotIncidentContext | None = None


async def assemble_context(
    db: AsyncSession, *, organization_id: uuid.UUID, focus_incident_id: uuid.UUID | None = None
) -> CopilotContext:
    incidents = await query_service.list_incidents(
        db, organization_id=organization_id, status_filter=None, endpoint_id=None, limit=_MAX_INCIDENTS_IN_CONTEXT, offset=0
    )
    health = await query_service.get_latest_health(db, organization_id=organization_id, endpoint_id=None)

    incident_contexts = [await _to_incident_context(db, organization_id=organization_id, incident=i) for i in incidents]

    focused = None
    if focus_incident_id is not None:
        existing = next((ic for ic in incident_contexts if ic.incident_id == focus_incident_id), None)
        if existing is not None:
            focused = existing
        else:
            # Not in the recent list (e.g. already resolved) -- fetch it directly,
            # still tenant-scoped via get_incident_or_404.
            incident = await query_service.get_incident_or_404(db, organization_id=organization_id, incident_id=focus_incident_id)
            focused = await _to_incident_context(db, organization_id=organization_id, incident=incident)

    return CopilotContext(incidents=incident_contexts, health_snapshots=health, focused_incident=focused)


async def _to_incident_context(db: AsyncSession, *, organization_id: uuid.UUID, incident: Incident) -> CopilotIncidentContext:
    # list_rca_for_incident orders by created_at DESC -- index 0 is the latest entry.
    rca_entries = await query_service.list_rca_for_incident(db, organization_id=organization_id, incident_id=incident.id)
    latest_rca = rca_entries[0] if rca_entries else None
    return CopilotIncidentContext(
        incident_id=incident.id,
        title=incident.title,
        status=incident.status,
        severity=incident.severity,
        failure_category=incident.failure_category,
        summary=incident.summary,
        latest_rca=latest_rca,
    )
