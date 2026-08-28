from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth import invitation_service
from app.modules.auth.dependencies import AuthContext, get_optional_auth
from app.modules.auth.invitation_schemas import AcceptInvitationRequest, InvitationPublicOut
from app.modules.auth.schemas import TokenResponse

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.get("/{token}", response_model=InvitationPublicOut)
async def get_invitation(token: str, db: AsyncSession = Depends(get_db)):
    invitation, org = await invitation_service.get_invitation_by_token(db, raw_token=token)
    return InvitationPublicOut(
        organization_name=org.name,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
        expires_at=invitation.expires_at,
    )


@router.post("/accept", response_model=TokenResponse)
async def accept_invitation(
    payload: AcceptInvitationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_auth: AuthContext | None = Depends(get_optional_auth),
):
    return await invitation_service.accept_invitation(
        db, raw_token=payload.token, full_name=payload.full_name, password=payload.password,
        current_auth=current_auth, ip_address=request.client.host if request.client else None,
    )
