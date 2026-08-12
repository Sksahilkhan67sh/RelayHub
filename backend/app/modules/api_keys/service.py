from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key
from app.modules.api_keys.models import ApiKey
from app.modules.api_keys.schemas import ApiKeyCreatedResponse, CreateApiKeyRequest
from app.modules.audit import service as audit_service
from app.modules.audit.models import AuditAction


def mask_key(prefix: str) -> str:
    return f"{prefix}{'•' * 24}"


async def create_api_key(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    data: CreateApiKeyRequest,
    ip_address: str | None,
) -> ApiKeyCreatedResponse:
    full_key, prefix, key_hash = generate_api_key(live=data.environment.value == "live")

    expires_at = None
    if data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)

    key = ApiKey(
        organization_id=organization_id,
        name=data.name,
        environment=data.environment.value,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=data.scopes,
        created_by_user_id=actor_user_id,
        expires_at=expires_at,
    )
    db.add(key)
    await db.flush()

    await audit_service.record(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction.API_KEY_CREATED,
        resource_type="api_key",
        resource_id=str(key.id),
        metadata={"name": data.name, "environment": data.environment.value, "scopes": data.scopes},
        ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(key)

    return ApiKeyCreatedResponse(
        id=key.id,
        name=key.name,
        environment=key.environment,
        scopes=key.scopes,
        key=full_key,
        key_prefix=key.key_prefix,
        expires_at=key.expires_at,
        created_at=key.created_at,
    )


async def list_api_keys(db: AsyncSession, *, organization_id: uuid.UUID) -> list[ApiKey]:
    result = await db.execute(
        select(ApiKey).where(ApiKey.organization_id == organization_id).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def _get_key_or_404(db: AsyncSession, *, organization_id: uuid.UUID, key_id: uuid.UUID) -> ApiKey:
    key = (
        await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.organization_id == organization_id))
    ).scalar_one_or_none()
    if not key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API key not found")
    return key


async def revoke_api_key(
    db: AsyncSession, *, organization_id: uuid.UUID, key_id: uuid.UUID, actor_user_id: uuid.UUID, reason: str | None, ip_address: str | None
) -> ApiKey:
    key = await _get_key_or_404(db, organization_id=organization_id, key_id=key_id)
    if key.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="API key is already revoked")

    key.revoked_at = datetime.now(timezone.utc)
    key.revoked_reason = reason

    await audit_service.record(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction.API_KEY_REVOKED,
        resource_type="api_key",
        resource_id=str(key.id),
        metadata={"reason": reason},
        ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(key)
    return key


async def rotate_api_key(
    db: AsyncSession, *, organization_id: uuid.UUID, key_id: uuid.UUID, actor_user_id: uuid.UUID, ip_address: str | None
) -> ApiKeyCreatedResponse:
    """
    Rotation = revoke the old key and issue a brand new one with the same name/scopes/
    environment. We do NOT mutate the existing row's secret in place, since that would
    make the "one-time reveal" guarantee meaningless for anyone who already has the old
    key cached -- an explicit new key + explicit old-key revocation is the safer, more
    auditable pattern.
    """
    old_key = await _get_key_or_404(db, organization_id=organization_id, key_id=key_id)
    if old_key.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Cannot rotate a revoked API key")

    old_key.revoked_at = datetime.now(timezone.utc)
    old_key.revoked_reason = "rotated"

    from app.modules.api_keys.schemas import ApiKeyEnvironment, CreateApiKeyRequest

    new_key_data = CreateApiKeyRequest(
        name=old_key.name,
        environment=ApiKeyEnvironment(old_key.environment),
        scopes=list(old_key.scopes),
        expires_in_days=None,
    )
    full_key, prefix, key_hash = generate_api_key(live=old_key.environment == "live")
    new_key = ApiKey(
        organization_id=organization_id,
        name=new_key_data.name,
        environment=new_key_data.environment.value,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=new_key_data.scopes,
        created_by_user_id=actor_user_id,
    )
    db.add(new_key)
    await db.flush()

    await audit_service.record(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction.API_KEY_ROTATED,
        resource_type="api_key",
        resource_id=str(new_key.id),
        metadata={"replaced_key_id": str(old_key.id)},
        ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(new_key)

    return ApiKeyCreatedResponse(
        id=new_key.id,
        name=new_key.name,
        environment=new_key.environment,
        scopes=new_key.scopes,
        key=full_key,
        key_prefix=new_key.key_prefix,
        expires_at=new_key.expires_at,
        created_at=new_key.created_at,
    )
