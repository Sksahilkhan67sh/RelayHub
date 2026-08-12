from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.stripe_client import StripeClient, StripeWebhookVerificationError
from app.modules.billing.models import Invoice, Plan, PlanTier, Subscription, SubscriptionStatus, UsageRecord
from app.modules.billing.schemas import CheckoutSessionOut, PortalSessionOut, UsageOut
from app.modules.delivery.models import DeliveryJob
from app.modules.endpoints.models import Endpoint

DEFAULT_PLAN_SPECS: dict[str, dict] = {
    PlanTier.FREE.value: dict(
        name="Free", price_cents=0, max_deliveries_per_month=1000, max_endpoints=1, log_retention_days=7,
        rate_limit_per_minute=100, rate_limit_per_hour=1000, rate_limit_per_day=10000, allow_overage=False,
        has_advanced_analytics=False, has_priority_support=False, has_sso=False,
    ),
    PlanTier.STARTER.value: dict(
        name="Starter", price_cents=2900, max_deliveries_per_month=100_000, max_endpoints=20, log_retention_days=30,
        rate_limit_per_minute=200, rate_limit_per_hour=2000, rate_limit_per_day=20000, allow_overage=True,
        has_advanced_analytics=False, has_priority_support=True, has_sso=False,
    ),
    PlanTier.PRO.value: dict(
        name="Pro", price_cents=9900, max_deliveries_per_month=5_000_000, max_endpoints=None, log_retention_days=90,
        rate_limit_per_minute=500, rate_limit_per_hour=5000, rate_limit_per_day=50000, allow_overage=True,
        has_advanced_analytics=True, has_priority_support=True, has_sso=False,
    ),
    PlanTier.ENTERPRISE.value: dict(
        name="Enterprise", price_cents=0, max_deliveries_per_month=None, max_endpoints=None, log_retention_days=365,
        rate_limit_per_minute=1000, rate_limit_per_hour=10000, rate_limit_per_day=100000, allow_overage=True,
        has_advanced_analytics=True, has_priority_support=True, has_sso=True,
    ),
}

TRIAL_ELIGIBLE_TIERS = {PlanTier.STARTER.value, PlanTier.PRO.value}
DEFAULT_TRIAL_DAYS = 14
USAGE_ALERT_THRESHOLDS = [0.8, 1.0]


async def get_or_create_plan(db: AsyncSession, tier: str) -> Plan:
    plan = (await db.execute(select(Plan).where(Plan.tier == tier))).scalar_one_or_none()
    if plan:
        return plan
    spec = DEFAULT_PLAN_SPECS[tier]
    plan = Plan(tier=tier, **spec)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def list_plans(db: AsyncSession) -> list[Plan]:
    for tier in DEFAULT_PLAN_SPECS:
        await get_or_create_plan(db, tier)
    result = await db.execute(select(Plan).order_by(Plan.price_cents))
    return list(result.scalars().all())


async def sync_organization_plan_fields(db: AsyncSession, *, organization_id: uuid.UUID, plan: Plan) -> None:
    from app.modules.auth.models import Organization

    org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalar_one()
    org.plan_id = plan.id
    org.log_retention_days = plan.log_retention_days
    await db.commit()


def _default_period() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_month = monthrange(now.year, now.month)[1]
    end = start + timedelta(days=days_in_month)
    return start, end


async def get_or_create_subscription(db: AsyncSession, *, organization_id: uuid.UUID) -> Subscription:
    existing = (
        await db.execute(select(Subscription).where(Subscription.organization_id == organization_id))
    ).scalar_one_or_none()
    if existing:
        return existing

    free_plan = await get_or_create_plan(db, PlanTier.FREE.value)
    period_start, period_end = _default_period()
    subscription = Subscription(
        organization_id=organization_id,
        plan_id=free_plan.id,
        status=SubscriptionStatus.ACTIVE.value,
        current_period_start=period_start,
        current_period_end=period_end,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    await sync_organization_plan_fields(db, organization_id=organization_id, plan=free_plan)
    return subscription


async def get_subscription_with_plan(db: AsyncSession, *, organization_id: uuid.UUID) -> Subscription:
    subscription = await get_or_create_subscription(db, organization_id=organization_id)
    plan = (await db.execute(select(Plan).where(Plan.id == subscription.plan_id))).scalar_one()
    subscription.plan = plan  # type: ignore[attr-defined]
    return subscription


async def create_checkout_session(
    db: AsyncSession, *, organization_id: uuid.UUID, owner_email: str, tier: str, success_url: str, cancel_url: str,
    stripe_client: StripeClient,
) -> CheckoutSessionOut:
    if tier not in (PlanTier.STARTER.value, PlanTier.PRO.value):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Checkout is only available for 'starter' and 'pro' -- Enterprise is contact-sales, Free requires no checkout.",
        )

    plan = await get_or_create_plan(db, tier)
    if not plan.stripe_price_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Plan '{tier}' has no Stripe price configured yet. Set Plan.stripe_price_id before enabling checkout.",
        )

    trial_days = DEFAULT_TRIAL_DAYS if tier in TRIAL_ELIGIBLE_TIERS else None
    result = stripe_client.create_checkout_session(
        customer_email=owner_email,
        price_id=plan.stripe_price_id,
        success_url=success_url,
        cancel_url=cancel_url,
        trial_days=trial_days,
        metadata={"organization_id": str(organization_id), "tier": tier},
    )
    return CheckoutSessionOut(checkout_url=result.checkout_url)


async def create_portal_session(
    db: AsyncSession, *, organization_id: uuid.UUID, return_url: str, stripe_client: StripeClient
) -> PortalSessionOut:
    subscription = await get_or_create_subscription(db, organization_id=organization_id)
    if not subscription.stripe_customer_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="No billing account exists yet -- upgrade to a paid plan first via checkout.",
        )
    result = stripe_client.create_portal_session(stripe_customer_id=subscription.stripe_customer_id, return_url=return_url)
    return PortalSessionOut(portal_url=result.portal_url)


def verify_and_parse_webhook(*, payload: bytes, signature_header: str, stripe_client: StripeClient) -> dict:
    try:
        return stripe_client.construct_webhook_event(payload=payload, signature_header=signature_header)
    except StripeWebhookVerificationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Invalid Stripe webhook signature: {e}") from e


async def handle_webhook_event(db: AsyncSession, *, event: dict) -> None:
    event_type = event.get("type", "")
    data_object = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(db, data_object)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(db, data_object)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(db, data_object)
    elif event_type == "invoice.paid":
        await _handle_invoice(db, data_object, status_override="paid")
    elif event_type == "invoice.payment_failed":
        await _handle_invoice(db, data_object, status_override="open")
        await _handle_payment_failed(db, data_object)


async def _handle_checkout_completed(db: AsyncSession, data_object: dict) -> None:
    metadata = data_object.get("metadata", {})
    organization_id = metadata.get("organization_id")
    tier = metadata.get("tier")
    if not organization_id or not tier:
        return

    plan = await get_or_create_plan(db, tier)
    subscription = await get_or_create_subscription(db, organization_id=uuid.UUID(organization_id))
    subscription.plan_id = plan.id
    subscription.status = SubscriptionStatus.ACTIVE.value
    subscription.stripe_customer_id = data_object.get("customer")
    subscription.stripe_subscription_id = data_object.get("subscription")
    await db.commit()
    await sync_organization_plan_fields(db, organization_id=uuid.UUID(organization_id), plan=plan)


async def _find_subscription_by_stripe_id(db: AsyncSession, stripe_subscription_id: str) -> Subscription | None:
    return (
        await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id))
    ).scalar_one_or_none()


async def _handle_subscription_updated(db: AsyncSession, data_object: dict) -> None:
    stripe_subscription_id = data_object.get("id")
    subscription = await _find_subscription_by_stripe_id(db, stripe_subscription_id)
    if not subscription:
        return

    stripe_status = data_object.get("status", "active")
    subscription.status = stripe_status if stripe_status in [s.value for s in SubscriptionStatus] else SubscriptionStatus.ACTIVE.value
    subscription.cancel_at_period_end = bool(data_object.get("cancel_at_period_end", False))

    if data_object.get("current_period_start"):
        subscription.current_period_start = datetime.fromtimestamp(data_object["current_period_start"], tz=timezone.utc)
    if data_object.get("current_period_end"):
        subscription.current_period_end = datetime.fromtimestamp(data_object["current_period_end"], tz=timezone.utc)
    if data_object.get("trial_end"):
        subscription.trial_end = datetime.fromtimestamp(data_object["trial_end"], tz=timezone.utc)

    await db.commit()

    plan = (await db.execute(select(Plan).where(Plan.id == subscription.plan_id))).scalar_one()
    await sync_organization_plan_fields(db, organization_id=subscription.organization_id, plan=plan)


async def _handle_subscription_deleted(db: AsyncSession, data_object: dict) -> None:
    stripe_subscription_id = data_object.get("id")
    subscription = await _find_subscription_by_stripe_id(db, stripe_subscription_id)
    if not subscription:
        return

    subscription.status = SubscriptionStatus.CANCELED.value
    subscription.canceled_at = datetime.now(timezone.utc)

    free_plan = await get_or_create_plan(db, PlanTier.FREE.value)
    subscription.plan_id = free_plan.id
    await db.commit()
    await sync_organization_plan_fields(db, organization_id=subscription.organization_id, plan=free_plan)


async def _handle_invoice(db: AsyncSession, data_object: dict, *, status_override: str) -> None:
    stripe_invoice_id = data_object.get("id")
    if not stripe_invoice_id:
        return

    existing = (
        await db.execute(select(Invoice).where(Invoice.stripe_invoice_id == stripe_invoice_id))
    ).scalar_one_or_none()

    stripe_subscription_id = data_object.get("subscription")
    subscription = await _find_subscription_by_stripe_id(db, stripe_subscription_id) if stripe_subscription_id else None
    organization_id = subscription.organization_id if subscription else None
    if organization_id is None:
        return

    period_start = datetime.fromtimestamp(data_object["period_start"], tz=timezone.utc) if data_object.get("period_start") else None
    period_end = datetime.fromtimestamp(data_object["period_end"], tz=timezone.utc) if data_object.get("period_end") else None

    if existing:
        existing.status = data_object.get("status", status_override)
        existing.amount_cents = data_object.get("amount_paid") or data_object.get("amount_due") or existing.amount_cents
    else:
        db.add(
            Invoice(
                organization_id=organization_id,
                subscription_id=subscription.id if subscription else None,
                stripe_invoice_id=stripe_invoice_id,
                amount_cents=data_object.get("amount_paid") or data_object.get("amount_due") or 0,
                status=data_object.get("status", status_override),
                invoice_pdf_url=data_object.get("invoice_pdf"),
                period_start=period_start,
                period_end=period_end,
            )
        )
    await db.commit()


async def _handle_payment_failed(db: AsyncSession, data_object: dict) -> None:
    from app.common.notification_client import get_notification_dispatcher
    from app.modules.alerts import service as alerts_service
    from app.modules.alerts.models import AlertConditionType

    stripe_subscription_id = data_object.get("subscription")
    subscription = await _find_subscription_by_stripe_id(db, stripe_subscription_id) if stripe_subscription_id else None
    if not subscription:
        return

    subscription.status = SubscriptionStatus.PAST_DUE.value
    await db.commit()

    await alerts_service.trigger_alert(
        db,
        organization_id=subscription.organization_id,
        condition_type=AlertConditionType.BILLING_THRESHOLD.value,
        message="A payment for your RelayHub subscription failed. Please update your payment method to avoid service interruption.",
        resource_id=str(subscription.id),
        metadata={"subscription_id": str(subscription.id)},
        notification_dispatcher=get_notification_dispatcher(),
    )


async def get_current_usage(db: AsyncSession, *, organization_id: uuid.UUID) -> UsageOut:
    subscription = await get_subscription_with_plan(db, organization_id=organization_id)
    plan: Plan = subscription.plan  # type: ignore[attr-defined]

    period_start = subscription.current_period_start or _default_period()[0]
    period_end = subscription.current_period_end or _default_period()[1]

    delivery_rows = (
        await db.execute(
            select(DeliveryJob).where(
                DeliveryJob.organization_id == organization_id,
                DeliveryJob.queued_at >= period_start,
                DeliveryJob.queued_at < period_end,
                DeliveryJob.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    delivery_count = len(delivery_rows)

    endpoint_count = len(
        (
            await db.execute(
                select(Endpoint).where(Endpoint.organization_id == organization_id, Endpoint.deleted_at.is_(None))
            )
        ).scalars().all()
    )

    existing_record = (
        await db.execute(
            select(UsageRecord).where(
                UsageRecord.organization_id == organization_id, UsageRecord.period_start == period_start
            )
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing_record:
        existing_record.delivery_count = delivery_count
        existing_record.computed_at = now
    else:
        db.add(
            UsageRecord(
                organization_id=organization_id, period_start=period_start, period_end=period_end,
                delivery_count=delivery_count, computed_at=now,
            )
        )
    await db.commit()

    percent_used = (delivery_count / plan.max_deliveries_per_month) if plan.max_deliveries_per_month else None

    if percent_used is not None:
        await _maybe_trigger_usage_alert(db, organization_id=organization_id, percent_used=percent_used)

    return UsageOut(
        period_start=period_start, period_end=period_end, delivery_count=delivery_count,
        max_deliveries_per_month=plan.max_deliveries_per_month, percent_used=percent_used,
        endpoint_count=endpoint_count, max_endpoints=plan.max_endpoints,
    )


async def _maybe_trigger_usage_alert(db: AsyncSession, *, organization_id: uuid.UUID, percent_used: float) -> None:
    from app.common.notification_client import get_notification_dispatcher
    from app.modules.alerts import service as alerts_service
    from app.modules.alerts.models import AlertConditionType

    crossed = max((t for t in USAGE_ALERT_THRESHOLDS if percent_used >= t), default=None)
    if crossed is None:
        return

    await alerts_service.trigger_alert(
        db,
        organization_id=organization_id,
        condition_type=AlertConditionType.BILLING_THRESHOLD.value,
        message=f"Usage has reached {crossed * 100:.0f}% of your plan's monthly delivery limit.",
        resource_id=f"usage-{crossed}",
        metadata={"percent_used": percent_used},
        notification_dispatcher=get_notification_dispatcher(),
    )


async def enforce_endpoint_limit(db: AsyncSession, *, organization_id: uuid.UUID) -> None:
    subscription = await get_subscription_with_plan(db, organization_id=organization_id)
    plan: Plan = subscription.plan  # type: ignore[attr-defined]
    if plan.max_endpoints is None:
        return

    current_count = len(
        (
            await db.execute(
                select(Endpoint).where(Endpoint.organization_id == organization_id, Endpoint.deleted_at.is_(None))
            )
        ).scalars().all()
    )
    if current_count >= plan.max_endpoints:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Endpoint limit reached for the '{plan.tier}' plan ({plan.max_endpoints} max). Upgrade to add more.",
        )


async def enforce_delivery_limit(db: AsyncSession, *, organization_id: uuid.UUID) -> None:
    usage = await get_current_usage(db, organization_id=organization_id)
    if usage.max_deliveries_per_month is None:
        return
    if usage.delivery_count < usage.max_deliveries_per_month:
        return

    subscription = await get_subscription_with_plan(db, organization_id=organization_id)
    plan: Plan = subscription.plan  # type: ignore[attr-defined]
    if plan.allow_overage:
        return

    raise HTTPException(
        status.HTTP_402_PAYMENT_REQUIRED,
        detail=f"Monthly delivery limit reached for the '{plan.tier}' plan ({usage.max_deliveries_per_month} max). Upgrade to continue.",
    )


async def list_invoices(db: AsyncSession, *, organization_id: uuid.UUID) -> list[Invoice]:
    result = await db.execute(
        select(Invoice).where(Invoice.organization_id == organization_id).order_by(Invoice.created_at.desc())
    )
    return list(result.scalars().all())
