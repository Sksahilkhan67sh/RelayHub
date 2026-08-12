import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role
from app.modules.endpoints import service
from app.modules.endpoints.schemas import (
    CreateEndpointRequest,
    EndpointOut,
    EndpointSecretOut,
    RotateSecretRequest,
    UpdateEndpointRequest,
)

router = APIRouter(prefix="/endpoints", tags=["endpoints"])


@router.post("", response_model=EndpointOut, status_code=status.HTTP_201_CREATED)
async def create_endpoint(
    payload: CreateEndpointRequest,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    endpoint, _raw_secret = await service.create_endpoint(
        db,
        organization_id=auth.organization_id,
        actor_user_id=auth.user_id,
        data=payload,
        ip_address=request.client.host if request.client else None,
    )
    return endpoint


@router.get("", response_model=list[EndpointOut])
async def list_endpoints(auth: AuthContext = Depends(require_role(Role.VIEWER)), db: AsyncSession = Depends(get_db)):
    return await service.list_endpoints(db, organization_id=auth.organization_id)


@router.get("/{endpoint_id}", response_model=EndpointOut)
async def get_endpoint(
    endpoint_id: uuid.UUID, auth: AuthContext = Depends(require_role(Role.VIEWER)), db: AsyncSession = Depends(get_db)
):
    return await service.get_endpoint(db, organization_id=auth.organization_id, endpoint_id=endpoint_id)


@router.patch("/{endpoint_id}", response_model=EndpointOut)
async def update_endpoint(
    endpoint_id: uuid.UUID,
    payload: UpdateEndpointRequest,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_endpoint(
        db,
        organization_id=auth.organization_id,
        endpoint_id=endpoint_id,
        actor_user_id=auth.user_id,
        data=payload,
        ip_address=request.client.host if request.client else None,
    )


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(
    endpoint_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_endpoint(
        db,
        organization_id=auth.organization_id,
        endpoint_id=endpoint_id,
        actor_user_id=auth.user_id,
        ip_address=request.client.host if request.client else None,
    )


@router.post("/{endpoint_id}/rotate-secret", response_model=EndpointSecretOut)
async def rotate_secret(
    endpoint_id: uuid.UUID,
    payload: RotateSecretRequest,
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await service.rotate_secret(
        db, organization_id=auth.organization_id, endpoint_id=endpoint_id, grace_period_hours=payload.grace_period_hours
    )
