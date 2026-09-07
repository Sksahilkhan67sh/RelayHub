from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import FeatureFlag, FeatureFlagOverride
from app.modules.audit import service as audit_service
from app.modules.audit.models import AuditAction
from app.modules.auth.models import Organization


async def create_feature_flag(db: AsyncSession, *, key: str, description: str, is_enabled_globally: bool) -> FeatureFlag:
    existing = (await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Feature flag '{key}' already exists")
    flag = FeatureFlag(key=key, description=description, is_enabled_globally=is_enabled_globally)
    db.add(flag)
    await db.commit()
    await db.refresh(flag)
    return flag


async def list_feature_flags(db: AsyncSession) -> list[FeatureFlag]:
    return list((await db.execute(select(FeatureFlag).order_by(FeatureFlag.key))).scalars().all())


async def _get_flag_or_404(db: AsyncSession, key: str) -> FeatureFlag:
    flag = (await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))).scalar_one_or_none()
    if not flag:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Feature flag not found")
    return flag


async def update_feature_flag(
    db: AsyncSession, *, key: str, description: str | None, is_enabled_globally: bool | None,
    actor_user_id: uuid.UUID, ip_address: str | None,
) -> FeatureFlag:
    flag = await _get_flag_or_404(db, key)
    if description is not None:
        flag.description = description
    if is_enabled_globally is not None:
        flag.is_enabled_globally = is_enabled_globally

    await audit_service.record(
        db, organization_id=None, actor_user_id=actor_user_id, action=AuditAction.ADMIN_FEATURE_FLAG_UPDATED,
        resource_type="feature_flag", resource_id=key, metadata={"is_enabled_globally": is_enabled_globally}, ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(flag)
    return flag


async def set_feature_flag_override(db: AsyncSession, *, key: str, organization_id: uuid.UUID, is_enabled: bool) -> None:
    flag = await _get_flag_or_404(db, key)
    existing = (
        await db.execute(
            select(FeatureFlagOverride).where(
                FeatureFlagOverride.flag_id == flag.id, FeatureFlagOverride.organization_id == organization_id
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.is_enabled = is_enabled
    else:
        db.add(FeatureFlagOverride(flag_id=flag.id, organization_id=organization_id, is_enabled=is_enabled))
    await db.commit()


async def list_feature_flag_overrides(db: AsyncSession, *, key: str) -> list[tuple[FeatureFlagOverride, str]]:
    """Returns (override, organization_name) pairs, newest first."""
    flag = await _get_flag_or_404(db, key)
    rows = (
        await db.execute(
            select(FeatureFlagOverride, Organization.name)
            .join(Organization, Organization.id == FeatureFlagOverride.organization_id)
            .where(FeatureFlagOverride.flag_id == flag.id)
            .order_by(FeatureFlagOverride.created_at.desc())
        )
    ).all()
    return [(override, org_name) for override, org_name in rows]


async def is_feature_enabled(db: AsyncSession, *, key: str, organization_id: uuid.UUID | None = None) -> bool:
    """Public helper other modules can use: `if await is_feature_enabled(db, key='x', organization_id=org.id): ...`"""
    flag = (await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))).scalar_one_or_none()
    if not flag:
        return False
    if organization_id is not None:
        override = (
            await db.execute(
                select(FeatureFlagOverride).where(
                    FeatureFlagOverride.flag_id == flag.id, FeatureFlagOverride.organization_id == organization_id
                )
            )
        ).scalar_one_or_none()
        if override is not None:
            return override.is_enabled
    return flag.is_enabled_globally
