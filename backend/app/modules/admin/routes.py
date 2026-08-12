import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.queue_client import QueueClient, get_queue_client
from app.db.session import get_db
from app.modules.admin import service
from app.modules.admin.schemas import (
    AbuseReportOut,
    AdminOrganizationOut,
    BillingOverviewOut,
    CreateAbuseReportRequest,
    CreateFeatureFlagRequest,
    FeatureFlagOut,
    FeatureFlagOverrideOut,
    ForceActionResponse,
    ImpersonationResponse,
    QueueDepthOut,
    ResolveAbuseReportRequest,
    SetFeatureFlagOverrideRequest,
    SuspendOrganizationRequest,
    SystemHealthOut,
    UpdateFeatureFlagRequest,
)
from app.modules.auth.dependencies import AuthContext, require_platform_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/organizations", response_model=list[AdminOrganizationOut])
async def list_organizations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_organizations(db, limit=limit, offset=offset)


@router.post("/organizations/{organization_id}/suspend", response_model=AdminOrganizationOut)
async def suspend_organization(
    organization_id: uuid.UUID,
    payload: SuspendOrganizationRequest,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    org = await service.suspend_organization(
        db, organization_id=organization_id, reason=payload.reason, actor_user_id=auth.user_id,
        ip_address=request.client.host if request.client else None,
    )
    orgs = await service.list_organizations(db, limit=1, offset=0)
    match = next((o for o in orgs if o["id"] == org.id), None)
    return match or {
        "id": org.id, "name": org.name, "slug": org.slug, "is_suspended": org.is_suspended,
        "suspension_reason": org.suspension_reason, "plan_tier": None, "subscription_status": None,
        "member_count": 0, "endpoint_count": 0, "created_at": org.created_at,
    }


@router.post("/organizations/{organization_id}/unsuspend", response_model=ForceActionResponse)
async def unsuspend_organization(
    organization_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    org = await service.unsuspend_organization(
        db, organization_id=organization_id, actor_user_id=auth.user_id,
        ip_address=request.client.host if request.client else None,
    )
    return ForceActionResponse(id=org.id, status="unsuspended")


@router.post("/organizations/{organization_id}/impersonate", response_model=ImpersonationResponse)
async def impersonate_organization(
    organization_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    token, email, expires_in = await service.impersonate_organization_owner(
        db, organization_id=organization_id, actor_user_id=auth.user_id,
        ip_address=request.client.host if request.client else None,
    )
    return ImpersonationResponse(access_token=token, impersonated_user_email=email, expires_in=expires_in)


@router.get("/queues", response_model=QueueDepthOut)
async def get_queue_depth(auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    return await service.get_queue_depth(db)


@router.get("/system-health", response_model=SystemHealthOut)
async def get_system_health(auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    return await service.get_system_health(db)


@router.get("/billing-overview", response_model=BillingOverviewOut)
async def get_billing_overview(auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    return await service.get_billing_overview(db)


@router.get("/logs")
async def admin_global_logs(
    organization_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    jobs = await service.admin_search_delivery_jobs(
        db, organization_id=organization_id, status_filter=status_filter, limit=limit, offset=offset
    )
    return [
        {
            "id": j.id, "organization_id": j.organization_id, "event_id": j.event_id, "endpoint_id": j.endpoint_id,
            "status": j.status, "attempt_number": j.attempt_number, "queued_at": j.queued_at, "completed_at": j.completed_at,
        }
        for j in jobs
    ]


@router.post("/delivery-jobs/{job_id}/force-retry", response_model=ForceActionResponse)
async def force_retry_delivery_job(
    job_id: uuid.UUID, request: Request, auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db),
    queue_client: QueueClient = Depends(get_queue_client),
):
    job = await service.force_retry_delivery_job(
        db, job_id=job_id, actor_user_id=auth.user_id, ip_address=request.client.host if request.client else None,
        queue_client=queue_client,
    )
    return ForceActionResponse(id=job.id, status=job.status)


@router.post("/delivery-jobs/{job_id}/force-cancel", response_model=ForceActionResponse)
async def force_cancel_delivery_job(
    job_id: uuid.UUID, request: Request, auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)
):
    job = await service.force_cancel_delivery_job(
        db, job_id=job_id, actor_user_id=auth.user_id, ip_address=request.client.host if request.client else None
    )
    return ForceActionResponse(id=job.id, status=job.status)


@router.post("/feature-flags", response_model=FeatureFlagOut)
async def create_feature_flag(
    payload: CreateFeatureFlagRequest, auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)
):
    return await service.create_feature_flag(
        db, key=payload.key, description=payload.description, is_enabled_globally=payload.is_enabled_globally
    )


@router.get("/feature-flags", response_model=list[FeatureFlagOut])
async def list_feature_flags(auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)):
    return await service.list_feature_flags(db)


@router.patch("/feature-flags/{key}", response_model=FeatureFlagOut)
async def update_feature_flag(
    key: str, payload: UpdateFeatureFlagRequest, request: Request,
    auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db),
):
    return await service.update_feature_flag(
        db, key=key, description=payload.description, is_enabled_globally=payload.is_enabled_globally,
        actor_user_id=auth.user_id, ip_address=request.client.host if request.client else None,
    )


@router.post("/feature-flags/{key}/override")
async def set_feature_flag_override(
    key: str, payload: SetFeatureFlagOverrideRequest, auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)
):
    await service.set_feature_flag_override(db, key=key, organization_id=payload.organization_id, is_enabled=payload.is_enabled)
    return {"key": key, "organization_id": str(payload.organization_id), "is_enabled": payload.is_enabled}


@router.get("/feature-flags/{key}/overrides", response_model=list[FeatureFlagOverrideOut])
async def list_feature_flag_overrides(
    key: str, auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)
):
    rows = await service.list_feature_flag_overrides(db, key=key)
    return [
        FeatureFlagOverrideOut(
            id=override.id, flag_id=override.flag_id, organization_id=override.organization_id,
            organization_name=org_name, is_enabled=override.is_enabled,
            created_at=override.created_at, updated_at=override.updated_at,
        )
        for override, org_name in rows
    ]


@router.post("/abuse-reports", response_model=AbuseReportOut)
async def create_abuse_report(
    payload: CreateAbuseReportRequest, auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)
):
    return await service.create_abuse_report(
        db, organization_id=payload.organization_id, reason=payload.reason, reported_by_user_id=auth.user_id
    )


@router.get("/abuse-reports", response_model=list[AbuseReportOut])
async def list_abuse_reports(
    status: str | None = Query(default=None), auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db)
):
    return await service.list_abuse_reports(db, status_filter=status)


@router.patch("/abuse-reports/{report_id}", response_model=AbuseReportOut)
async def resolve_abuse_report(
    report_id: uuid.UUID, payload: ResolveAbuseReportRequest, request: Request,
    auth: AuthContext = Depends(require_platform_admin), db: AsyncSession = Depends(get_db),
):
    return await service.resolve_abuse_report(
        db, report_id=report_id, new_status=payload.status, resolution_notes=payload.resolution_notes,
        actor_user_id=auth.user_id, ip_address=request.client.host if request.client else None,
    )
