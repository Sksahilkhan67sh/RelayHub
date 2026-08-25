from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.notification_client import NotificationDispatcher, get_notification_dispatcher
from app.db.session import get_db
from app.modules.auth import password_reset_service, service
from app.modules.auth.dependencies import (
    AuthContext,
    enforce_forgot_password_rate_limit,
    enforce_login_rate_limit,
    enforce_refresh_rate_limit,
    get_current_auth,
)
from app.modules.auth.models import Membership, Organization, User
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MeResponse,
    OrganizationOut,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user, org = await service.register_user(db, payload)
    membership = (
        await db.execute(select(Membership).where(Membership.user_id == user.id, Membership.organization_id == org.id))
    ).scalar_one()
    return await service._issue_token_pair(
        db, user, membership, ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _rate_limit_check: None = Depends(enforce_login_rate_limit),
):
    return await service.authenticate(
        db, payload.email, payload.password,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit_check: None = Depends(enforce_refresh_rate_limit),
):
    return await service.refresh_access_token(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(auth: AuthContext = Depends(get_current_auth), db: AsyncSession = Depends(get_db)):
    await service.revoke_all_sessions(db, auth.user_id)


@router.get("/me", response_model=MeResponse)
async def me(auth: AuthContext = Depends(get_current_auth), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == auth.user_id))).scalar_one()
    org = (await db.execute(select(Organization).where(Organization.id == auth.organization_id))).scalar_one()
    return MeResponse(user=UserOut.model_validate(user), organization=OrganizationOut.model_validate(org), role=auth.role)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    notification_dispatcher: NotificationDispatcher = Depends(get_notification_dispatcher),
    _rate_limit_check: None = Depends(enforce_forgot_password_rate_limit),
):
    await password_reset_service.request_password_reset(
        db, email=payload.email, notification_dispatcher=notification_dispatcher,
        ip_address=request.client.host if request.client else None,
    )
    # Same response regardless of whether the email exists -- never leaks account existence.
    return ForgotPasswordResponse(message=password_reset_service.GENERIC_FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(payload: ResetPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await password_reset_service.confirm_password_reset(
        db, raw_token=payload.token, new_password=payload.new_password,
        ip_address=request.client.host if request.client else None,
    )
