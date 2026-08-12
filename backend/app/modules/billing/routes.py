from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.stripe_client import StripeClient, get_stripe_client
from app.db.session import get_db
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role, User
from app.modules.billing import service
from app.modules.billing.schemas import (
    CheckoutSessionOut,
    CreateCheckoutSessionRequest,
    InvoiceOut,
    PlanOut,
    PortalSessionOut,
    PortalSessionRequest,
    SubscriptionOut,
    UsageOut,
)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(db: AsyncSession = Depends(get_db)):
    return await service.list_plans(db)


@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(auth: AuthContext = Depends(require_role(Role.VIEWER)), db: AsyncSession = Depends(get_db)):
    subscription = await service.get_subscription_with_plan(db, organization_id=auth.organization_id)
    return SubscriptionOut(
        id=subscription.id,
        plan=PlanOut.model_validate(subscription.plan),  # type: ignore[attr-defined]  # dynamically attached in get_subscription_with_plan
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        trial_end=subscription.trial_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
    )


@router.get("/usage", response_model=UsageOut)
async def get_usage(auth: AuthContext = Depends(require_role(Role.VIEWER)), db: AsyncSession = Depends(get_db)):
    return await service.get_current_usage(db, organization_id=auth.organization_id)


@router.get("/invoices", response_model=list[InvoiceOut])
async def list_invoices(auth: AuthContext = Depends(require_role(Role.VIEWER)), db: AsyncSession = Depends(get_db)):
    return await service.list_invoices(db, organization_id=auth.organization_id)


@router.post("/checkout", response_model=CheckoutSessionOut)
async def create_checkout_session(
    payload: CreateCheckoutSessionRequest,
    auth: AuthContext = Depends(require_role(Role.OWNER)),
    db: AsyncSession = Depends(get_db),
    stripe_client: StripeClient = Depends(get_stripe_client),
):
    owner = (await db.execute(select(User).where(User.id == auth.user_id))).scalar_one()
    return await service.create_checkout_session(
        db,
        organization_id=auth.organization_id,
        owner_email=owner.email,
        tier=payload.tier,
        success_url=payload.success_url,
        cancel_url=payload.cancel_url,
        stripe_client=stripe_client,
    )


@router.post("/portal", response_model=PortalSessionOut)
async def create_portal_session(
    payload: PortalSessionRequest,
    auth: AuthContext = Depends(require_role(Role.OWNER)),
    db: AsyncSession = Depends(get_db),
    stripe_client: StripeClient = Depends(get_stripe_client),
):
    return await service.create_portal_session(
        db, organization_id=auth.organization_id, return_url=payload.return_url, stripe_client=stripe_client
    )


@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_client: StripeClient = Depends(get_stripe_client),
):
    """
    Called by Stripe itself -- no auth (Stripe can't present our JWT/API-key
    schemes), verified instead by the webhook signature per Stripe's own model.
    """
    payload = await request.body()
    signature_header = request.headers.get("stripe-signature", "")
    if not signature_header:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing Stripe-Signature header")

    event = service.verify_and_parse_webhook(payload=payload, signature_header=signature_header, stripe_client=stripe_client)
    await service.handle_webhook_event(db, event=event)
