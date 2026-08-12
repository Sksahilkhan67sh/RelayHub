from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_secret
from app.modules.audit import service as audit_service
from app.modules.audit.models import AuditAction
from app.modules.endpoints.models import (
    DEFAULT_FAILURE_STREAK_THRESHOLD,
    Endpoint,
    EndpointHealth,
    EndpointSecret,
)
from app.modules.endpoints.schemas import (
    CreateEndpointRequest,
    EndpointSecretOut,
    UpdateEndpointRequest,
)


def _generate_signing_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(32)}"


async def create_endpoint(
    db: AsyncSession, *, organization_id: uuid.UUID, actor_user_id: uuid.UUID, data: CreateEndpointRequest, ip_address: str | None
) -> tuple[Endpoint, str]:
    from app.modules.billing import service as billing_service

    await billing_service.enforce_endpoint_limit(db, organization_id=organization_id)

    endpoint = Endpoint(
        organization_id=organization_id,
        name=data.name,
        description=data.description,
        url=data.url,
        environment=data.environment.value,
        custom_headers=data.custom_headers,
        timeout_seconds=data.timeout_seconds,
        subscribed_event_types=data.subscribed_event_types,
        ip_allowlist=data.ip_allowlist,
        tls_verification_enabled=data.tls_verification_enabled,
        max_retry_attempts=data.max_retry_attempts,
        health_status=EndpointHealth.UNKNOWN.value,
    )
    db.add(endpoint)
    await db.flush()

    raw_secret = _generate_signing_secret()
    secret_row = EndpointSecret(
        endpoint_id=endpoint.id,
        encrypted_secret=encrypt_secret(raw_secret),
        is_primary=True,
    )
    db.add(secret_row)

    await audit_service.record(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction.ENDPOINT_CREATED,
        resource_type="endpoint",
        resource_id=str(endpoint.id),
        metadata={"name": data.name, "url": data.url, "environment": data.environment.value},
        ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(endpoint)
    return endpoint, raw_secret


async def list_endpoints(db: AsyncSession, *, organization_id: uuid.UUID) -> list[Endpoint]:
    result = await db.execute(
        select(Endpoint)
        .where(Endpoint.organization_id == organization_id, Endpoint.deleted_at.is_(None))
        .order_by(Endpoint.created_at.desc())
    )
    return list(result.scalars().all())


async def _get_endpoint_or_404(db: AsyncSession, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID) -> Endpoint:
    endpoint = (
        await db.execute(
            select(Endpoint).where(
                Endpoint.id == endpoint_id, Endpoint.organization_id == organization_id, Endpoint.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    return endpoint


async def get_endpoint(db: AsyncSession, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID) -> Endpoint:
    return await _get_endpoint_or_404(db, organization_id=organization_id, endpoint_id=endpoint_id)


async def update_endpoint(
    db: AsyncSession, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID, actor_user_id: uuid.UUID, data: UpdateEndpointRequest, ip_address: str | None
) -> Endpoint:
    endpoint = await _get_endpoint_or_404(db, organization_id=organization_id, endpoint_id=endpoint_id)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(endpoint, field, value)

    await audit_service.record(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction.ENDPOINT_UPDATED,
        resource_type="endpoint",
        resource_id=str(endpoint.id),
        metadata={"updated_fields": list(updates.keys())},
        ip_address=ip_address,
    )
    await db.commit()
    await db.refresh(endpoint)
    return endpoint


async def delete_endpoint(
    db: AsyncSession, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID, actor_user_id: uuid.UUID, ip_address: str | None
) -> None:
    endpoint = await _get_endpoint_or_404(db, organization_id=organization_id, endpoint_id=endpoint_id)
    endpoint.deleted_at = datetime.now(timezone.utc)
    endpoint.is_active = False

    await audit_service.record(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=AuditAction.ENDPOINT_DELETED,
        resource_type="endpoint",
        resource_id=str(endpoint.id),
        metadata={},
        ip_address=ip_address,
    )
    await db.commit()


async def rotate_secret(
    db: AsyncSession, *, organization_id: uuid.UUID, endpoint_id: uuid.UUID, grace_period_hours: int
) -> EndpointSecretOut:
    endpoint = await _get_endpoint_or_404(db, organization_id=organization_id, endpoint_id=endpoint_id)

    now = datetime.now(timezone.utc)
    current_primary = (
        await db.execute(
            select(EndpointSecret).where(EndpointSecret.endpoint_id == endpoint.id, EndpointSecret.is_primary.is_(True))
        )
    ).scalar_one_or_none()

    if current_primary:
        current_primary.is_primary = False
        current_primary.grace_period_ends_at = now + timedelta(hours=grace_period_hours) if grace_period_hours else now

    raw_secret = _generate_signing_secret()
    new_secret = EndpointSecret(endpoint_id=endpoint.id, encrypted_secret=encrypt_secret(raw_secret), is_primary=True)
    db.add(new_secret)
    await db.commit()
    await db.refresh(new_secret)

    return EndpointSecretOut(
        id=new_secret.id, secret=raw_secret, grace_period_ends_at=new_secret.grace_period_ends_at, created_at=new_secret.created_at
    )


async def record_delivery_result(db: AsyncSession, *, endpoint: Endpoint, success: bool) -> Endpoint:
    """
    Called by the delivery worker after each attempt to update health status and
    drive the circuit breaker.
    """
    from app.common.notification_client import get_notification_dispatcher
    from app.modules.alerts import service as alerts_service
    from app.modules.alerts.models import AlertConditionType

    now = datetime.now(timezone.utc)
    was_paused_before = endpoint.paused_at is not None

    if success:
        endpoint.consecutive_failure_count = 0
        endpoint.last_success_at = now
        endpoint.health_status = EndpointHealth.HEALTHY.value
        if endpoint.paused_at is not None and endpoint.paused_reason == "auto-circuit-breaker":
            endpoint.paused_at = None
            endpoint.paused_reason = None
            endpoint.is_active = True
    else:
        endpoint.consecutive_failure_count += 1
        endpoint.last_failure_at = now
        if endpoint.consecutive_failure_count >= DEFAULT_FAILURE_STREAK_THRESHOLD:
            endpoint.health_status = EndpointHealth.UNHEALTHY.value
            endpoint.is_active = False
            endpoint.paused_at = now
            endpoint.paused_reason = "auto-circuit-breaker"
        elif endpoint.consecutive_failure_count >= DEFAULT_FAILURE_STREAK_THRESHOLD // 2:
            endpoint.health_status = EndpointHealth.DEGRADED.value
    await db.commit()
    await db.refresh(endpoint)

    just_paused = (not was_paused_before) and endpoint.paused_at is not None
    if just_paused:
        # Only fires at the moment of transition, not on every failure while already
        # paused -- that's what the dedup/throttle window in trigger_alert is also
        # there to guard against, but avoiding the call entirely here is cheaper and
        # more precise for this specific condition.
        await alerts_service.trigger_alert(
            db,
            organization_id=endpoint.organization_id,
            condition_type=AlertConditionType.ENDPOINT_DOWN.value,
            message=f"Endpoint '{endpoint.name}' ({endpoint.url}) has been automatically paused after "
            f"{endpoint.consecutive_failure_count} consecutive delivery failures.",
            resource_id=str(endpoint.id),
            metadata={"endpoint_id": str(endpoint.id), "consecutive_failure_count": endpoint.consecutive_failure_count},
            notification_dispatcher=get_notification_dispatcher(),
        )

    return endpoint
