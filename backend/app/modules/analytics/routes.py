"""
This router is deliberately mounted at two paths in main.py:

  /v1/analytics/...  -- the original, published path. Kept exactly as-is because
                         it's a public, documented API surface: the Node and Python
                         SDKs (sdks/node/src/resources/analytics.ts,
                         sdks/python/relayhub/resources/analytics.py) and the
                         public API reference docs (apps/web/lib/api-modules-data.ts)
                         all hard-code this path. Removing or renaming it would
                         break every existing customer integration.

  /v1/insights/...    -- an identical alias, added because "analytics" in a URL is
                         a very common ad-blocker/privacy-extension filter-list
                         pattern (EasyPrivacy and similar lists match the substring
                         regardless of first-party vs. third-party intent). The
                         RelayHub dashboard's own analytics page was intermittently
                         failing to load for users running common ad blockers,
                         because the browser extension was blocking the dashboard's
                         own first-party XHR to /v1/analytics/events-by-type as
                         `net::ERR_BLOCKED_BY_CLIENT` before it ever reached this
                         server. The first-party web dashboard (apps/web) now calls
                         /v1/insights/... instead; the SDKs and public docs
                         continue to reference /v1/analytics/... unchanged.

Both paths route through the exact same handler functions below -- there is no
duplicated logic, no risk of the two paths drifting apart in behavior, and no
API-key/session distinction between them (auth is identical either way).
"""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.analytics import service
from app.modules.analytics.schemas import (
    EndpointHealthOut,
    EventTypeVolume,
    SummaryOut,
    TimeSeriesBucket,
    TopEndpointOut,
)
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role

router = APIRouter(tags=["analytics"])


@router.get("/summary", response_model=SummaryOut)
async def summary(
    environment: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    data = await service.get_summary(
        db, organization_id=auth.organization_id, environment=environment, start_date=start_date, end_date=end_date
    )
    return SummaryOut(**data)


@router.get("/deliveries-over-time", response_model=list[TimeSeriesBucket])
async def deliveries_over_time(
    granularity: str = Query(default="hour", pattern="^(hour|day)$"),
    environment: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    rows = await service.get_deliveries_over_time(
        db,
        organization_id=auth.organization_id,
        granularity=granularity,
        environment=environment,
        start_date=start_date,
        end_date=end_date,
    )
    return [TimeSeriesBucket(**r) for r in rows]


@router.get("/events-by-type", response_model=list[EventTypeVolume])
async def events_by_type(
    environment: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    rows = await service.get_events_by_type(
        db, organization_id=auth.organization_id, environment=environment, start_date=start_date, end_date=end_date
    )
    return [EventTypeVolume(**r) for r in rows]


@router.get("/top-endpoints", response_model=list[TopEndpointOut])
async def top_endpoints(
    limit: int = Query(default=10, ge=1, le=50),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    rows = await service.get_top_endpoints(
        db, organization_id=auth.organization_id, limit=limit, start_date=start_date, end_date=end_date
    )
    return [TopEndpointOut(**r) for r in rows]


@router.get("/endpoint-health", response_model=list[EndpointHealthOut])
async def endpoint_health(
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    rows = await service.get_endpoint_health(db, organization_id=auth.organization_id)
    return [EndpointHealthOut(**r) for r in rows]


@router.get("/export")
async def export_analytics(
    report: str = Query(pattern="^(deliveries-over-time|top-endpoints)$"),
    granularity: str = Query(default="hour", pattern="^(hour|day)$"),
    environment: str | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    if report == "deliveries-over-time":
        rows = await service.get_deliveries_over_time(
            db, organization_id=auth.organization_id, granularity=granularity, environment=environment,
            start_date=start_date, end_date=end_date,
        )
        writer.writerow(["bucket", "total_count", "success_count", "failed_count"])
        for r in rows:
            writer.writerow([r["bucket"], r["total_count"], r["success_count"], r["failed_count"]])
    else:
        rows = await service.get_top_endpoints(db, organization_id=auth.organization_id, limit=50, start_date=start_date, end_date=end_date)
        writer.writerow(["endpoint_id", "name", "delivery_count", "success_count", "success_rate", "avg_latency_ms"])
        for r in rows:
            writer.writerow(
                [str(r["endpoint_id"]), r["name"], r["delivery_count"], r["success_count"], r["success_rate"], r["avg_latency_ms"]]
            )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=relayhub_{report}.csv"},
    )
