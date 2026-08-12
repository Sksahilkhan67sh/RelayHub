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

router = APIRouter(prefix="/analytics", tags=["analytics"])


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
