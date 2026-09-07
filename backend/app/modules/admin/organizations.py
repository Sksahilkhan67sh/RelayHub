from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit import service as audit_service
from app.modules.audit.models import AuditAction
from app.modules.auth.models import Membership, Organization, Role, User
from app.modules.billing.models import Plan, Subscription
from app.modules.endpoints.models import Endpoint


async def list_organizations(db: AsyncSession, *, limit: int = 50, offset: int = 0) -> list[dict]:
    orgs = (
        await db.execute(select(Organization).order_by(Organization.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()

    results = []
    for org in orgs:
        member_count = (
            await db.execute(select(func.count(Membership.id)).where(Membership.organization_id == org.id))
        ).scalar_one()
        endpoint_count = (
            await db.execute(
                select(func.count(Endpoint.id)).where(Endpoint.organization_id == org.id, Endpoint.deleted_at.is_(None))
            )
        ).scalar_one()
        subscription = (
            await db.execute(select(Subscription).where(Subscription.organization_id == org.id))
        ).scalar_one_or_none()
        plan_tier = None
        if subscription:
            plan = (await db.execute(select(Plan).where(Plan.id == subscription.plan_id))).scalar_one_or_none()
            plan_tier = plan.tier if plan else None

        results.append(
            {
                "id": org.id, "name": org.name, "slug": org.slug, "is_suspended": org.is_suspended,
                "suspension_reason": org.suspension_reason, "plan_tier": plan_tier,
                "subscription_status": subscription.status if subscription else None,
                "member_count": member_count, "endpoint_count": endpoint_count, "created_at": org.created_at,
            }
        )
    return results


async def _get_org_or_404(db: AsyncSession, organization_id: uuid.UUID) -> Organization:
    org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalar_one_or_none()
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


async def suspend_organization(
    db: AsyncSession, *, organization_id: uuid.UUID, reason: str, actor_user_id: uuid.UUID, ip_address: str | None
) -> Organization:
    org = await _get_org_or_404(db, organization_id)
    org.is_suspended = True
    org.suspension_reason = reason

    await audit_service.record(
        db, organization_id=organization_id, actor_user_id=actor_user_id, action=AuditAction.ADMIN_ORG_SUSPENDED,
        resource_type="organization", resource_id=str(organization_id), metadata={"reason": reason}, ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(org)
    return org


async def unsuspend_organization(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_user_id: uuid.UUID, ip_address: str | None
) -> Organization:
    org = await _get_org_or_404(db, organization_id)
    org.is_suspended = False
    org.suspension_reason = None

    await audit_service.record(
        db, organization_id=organization_id, actor_user_id=actor_user_id, action=AuditAction.ADMIN_ORG_UNSUSPENDED,
        resource_type="organization", resource_id=str(organization_id), metadata={}, ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(org)
    return org


async def impersonate_organization_owner(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_user_id: uuid.UUID, ip_address: str | None
) -> tuple[str, str, int]:
    """
    Issues a short-lived (5 min, deliberately much shorter than a normal 15-min
    session) access token scoped to the org's owner, so a platform admin can debug a
    customer's exact view of the product. The audit log entry is the accountability
    mechanism -- this is intentionally logged loudly, not a quiet backdoor.
    """
    await _get_org_or_404(db, organization_id)  # raises 404 if the org doesn't exist

    owner_membership = (
        await db.execute(
            select(Membership).where(Membership.organization_id == organization_id, Membership.role == Role.OWNER.value)
        )
    ).scalar_one_or_none()
    if not owner_membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Organization has no owner to impersonate")

    owner = (await db.execute(select(User).where(User.id == owner_membership.user_id))).scalar_one()

    await audit_service.record(
        db, organization_id=organization_id, actor_user_id=actor_user_id, action=AuditAction.ADMIN_IMPERSONATION_STARTED,
        resource_type="organization", resource_id=str(organization_id),
        metadata={"impersonated_user_id": str(owner.id), "impersonated_email": owner.email}, ip_address=ip_address,
    )
    await db.commit()

    import jwt as pyjwt

    from app.core.config import settings

    now = datetime.now(timezone.utc)
    expires_in = 300
    payload = {
        "sub": str(owner.id), "org_id": str(organization_id), "role": owner_membership.role, "type": "access",
        "iat": now, "exp": now + timedelta(seconds=expires_in), "jti": str(uuid.uuid4()), "impersonated_by": str(actor_user_id),
    }
    token = pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, owner.email, expires_in
