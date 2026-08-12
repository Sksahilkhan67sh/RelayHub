import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.api_keys import service
from app.modules.api_keys.schemas import (
    ApiKeyCreatedResponse,
    ApiKeyOut,
    CreateApiKeyRequest,
    RevokeApiKeyRequest,
)
from app.modules.api_keys.service import mask_key
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def _to_out(key) -> ApiKeyOut:
    return ApiKeyOut(
        id=key.id,
        name=key.name,
        environment=key.environment,
        scopes=key.scopes,
        key_prefix=key.key_prefix,
        masked_key=mask_key(key.key_prefix),
        last_used_at=key.last_used_at,
        expires_at=key.expires_at,
        revoked_at=key.revoked_at,
        is_active=key.is_active,
        created_at=key.created_at,
    )


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    payload: CreateApiKeyRequest,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_api_key(
        db,
        organization_id=auth.organization_id,
        actor_user_id=auth.user_id,
        data=payload,
        ip_address=request.client.host if request.client else None,
    )


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    keys = await service.list_api_keys(db, organization_id=auth.organization_id)
    return [_to_out(k) for k in keys]


@router.post("/{key_id}/revoke", response_model=ApiKeyOut)
async def revoke_key(
    key_id: uuid.UUID,
    payload: RevokeApiKeyRequest,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    key = await service.revoke_api_key(
        db,
        organization_id=auth.organization_id,
        key_id=key_id,
        actor_user_id=auth.user_id,
        reason=payload.reason,
        ip_address=request.client.host if request.client else None,
    )
    return _to_out(key)


@router.post("/{key_id}/rotate", response_model=ApiKeyCreatedResponse)
async def rotate_key(
    key_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await service.rotate_api_key(
        db,
        organization_id=auth.organization_id,
        key_id=key_id,
        actor_user_id=auth.user_id,
        ip_address=request.client.host if request.client else None,
    )
