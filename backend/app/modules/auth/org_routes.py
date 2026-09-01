import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.notification_client import NotificationDispatcher, get_notification_dispatcher
from app.db.session import get_db
from app.modules.admin import service as admin_service
from app.modules.admin.schemas import AbuseReportOut
from app.modules.auth import invitation_service, org_service
from app.modules.auth.dependencies import AuthContext, get_current_auth, require_role
from app.modules.auth.invitation_schemas import CreateInvitationRequest, InvitationOut
from app.modules.auth.models import Role
from app.modules.auth.org_schemas import (
    CreateOrgAbuseReportRequest,
    InviteMemberRequest,
    MemberOut,
    UpdateMemberRoleRequest,
    UpdateOrganizationRequest,
)
from app.modules.auth.schemas import OrganizationOut

router = APIRouter(prefix="/org", tags=["organization"])


@router.get("/members", response_model=list[MemberOut])
async def list_members(auth: AuthContext = Depends(require_role(Role.VIEWER)), db: AsyncSession = Depends(get_db)):
    return await org_service.list_members(db, organization_id=auth.organization_id)


@router.post("/members", response_model=MemberOut)
async def invite_member(
    payload: InviteMemberRequest,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await org_service.invite_member(
        db, organization_id=auth.organization_id, email=payload.email, role=payload.role,
        actor_user_id=auth.user_id, actor_role=auth.role, ip_address=request.client.host if request.client else None,
    )


@router.patch("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_member_role(
    user_id: uuid.UUID,
    payload: UpdateMemberRoleRequest,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await org_service.update_member_role(
        db, organization_id=auth.organization_id, target_user_id=user_id, new_role=payload.role,
        actor_user_id=auth.user_id, actor_role=auth.role,
    )


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: uuid.UUID, auth: AuthContext = Depends(require_role(Role.ADMIN)), db: AsyncSession = Depends(get_db)
):
    await org_service.remove_member(db, organization_id=auth.organization_id, target_user_id=user_id, actor_role=auth.role)


@router.patch("", response_model=OrganizationOut)
async def update_organization(
    payload: UpdateOrganizationRequest,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await org_service.update_organization(db, organization_id=auth.organization_id, name=payload.name)


@router.post("/abuse-reports", response_model=AbuseReportOut, status_code=status.HTTP_201_CREATED)
async def create_org_abuse_report(
    payload: CreateOrgAbuseReportRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Self-service: any authenticated member (no elevated role required -- filing
    a report shouldn't need admin rights, only *seeing* the queue does, see
    list_org_abuse_reports below) can report something about their own org for
    platform review. Lands in the same table platform admins already review at
    /admin/abuse-reports.
    """
    return await admin_service.create_org_self_report(
        db, organization_id=auth.organization_id, reason=payload.reason, reported_by_user_id=auth.user_id
    )


@router.get("/abuse-reports", response_model=list[AbuseReportOut])
async def list_org_abuse_reports(
    auth: AuthContext = Depends(require_role(Role.ADMIN)), db: AsyncSession = Depends(get_db)
):
    """
    Read-only view of reports filed against the caller's own organization -- the
    org-scoped counterpart to /admin/abuse-reports (which is global and requires
    platform admin). Members are notified by title/body when a report is
    created or resolved (see notify_org_admins in admin/service.py) but had no
    page to actually read the report until now. Restricted to ADMIN/OWNER,
    matching who notify_org_admins fans the notification out to -- unlike the
    POST above, which any member can call.
    """
    return await admin_service.list_abuse_reports_for_org(db, organization_id=auth.organization_id)


@router.post("/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    payload: CreateInvitationRequest,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
    notification_dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    return await invitation_service.create_invitation(
        db, organization_id=auth.organization_id, email=payload.email, role=payload.role,
        actor_user_id=auth.user_id, actor_role=auth.role, notification_dispatcher=notification_dispatcher,
        ip_address=request.client.host if request.client else None,
    )


@router.get("/invitations", response_model=list[InvitationOut])
async def list_invitations(
    status_filter: str | None = Query(default=None, alias="status"),
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await invitation_service.list_invitations(db, organization_id=auth.organization_id, status_filter=status_filter)


@router.post("/invitations/{invitation_id}/revoke", response_model=InvitationOut)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await invitation_service.revoke_invitation(
        db, organization_id=auth.organization_id, invitation_id=invitation_id, actor_user_id=auth.user_id,
        ip_address=request.client.host if request.client else None,
    )


@router.post("/invitations/{invitation_id}/resend", response_model=InvitationOut)
async def resend_invitation(
    invitation_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
    notification_dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
):
    return await invitation_service.resend_invitation(
        db, organization_id=auth.organization_id, invitation_id=invitation_id, actor_user_id=auth.user_id,
        notification_dispatcher=notification_dispatcher, ip_address=request.client.host if request.client else None,
    )
