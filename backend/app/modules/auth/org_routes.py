import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.notification_client import NotificationDispatcher, get_notification_dispatcher
from app.db.session import get_db
from app.modules.auth import invitation_service, org_service
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.invitation_schemas import CreateInvitationRequest, InvitationOut
from app.modules.auth.models import Role
from app.modules.auth.org_schemas import (
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
        actor_user_id=auth.user_id, ip_address=request.client.host if request.client else None,
    )


@router.patch("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_member_role(
    user_id: uuid.UUID,
    payload: UpdateMemberRoleRequest,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await org_service.update_member_role(
        db, organization_id=auth.organization_id, target_user_id=user_id, new_role=payload.role, actor_user_id=auth.user_id
    )


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: uuid.UUID, auth: AuthContext = Depends(require_role(Role.ADMIN)), db: AsyncSession = Depends(get_db)
):
    await org_service.remove_member(db, organization_id=auth.organization_id, target_user_id=user_id)


@router.patch("", response_model=OrganizationOut)
async def update_organization(
    payload: UpdateOrganizationRequest,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await org_service.update_organization(db, organization_id=auth.organization_id, name=payload.name)


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
        actor_user_id=auth.user_id, notification_dispatcher=notification_dispatcher,
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
