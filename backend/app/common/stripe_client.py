"""
Stripe integration abstraction.

Same shape as every other external dependency in this codebase (queue_client,
notification_client, rate_limiter): a Protocol, a real implementation wrapping the
Stripe SDK, and an injectable fake for tests. This one is non-negotiable here --
this environment's network egress is allowlisted to specific domains and does not
include api.stripe.com, so business logic (webhook processing, plan enforcement,
checkout flow) MUST be testable without ever making a real Stripe call. The fake
also lets tests construct arbitrary webhook payloads without valid Stripe
signatures, which is exactly what's needed to test subscription lifecycle handling.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

from stripe import SignatureVerificationError


class StripeWebhookVerificationError(Exception):
    pass


@dataclass
class CheckoutSessionResult:
    session_id: str
    checkout_url: str


@dataclass
class PortalSessionResult:
    portal_url: str


class StripeClient(Protocol):
    def create_checkout_session(
        self, *, customer_email: str, price_id: str, success_url: str, cancel_url: str, trial_days: int | None = None,
        metadata: dict | None = None,
    ) -> CheckoutSessionResult: ...

    def create_portal_session(self, *, stripe_customer_id: str, return_url: str) -> PortalSessionResult: ...

    def construct_webhook_event(self, *, payload: bytes, signature_header: str) -> dict[str, Any]: ...

    def cancel_subscription(self, *, stripe_subscription_id: str, at_period_end: bool = True) -> None: ...


class RealStripeClient:
    def __init__(self, api_key: str, webhook_secret: str) -> None:
        import stripe

        stripe.api_key = api_key
        self._stripe = stripe
        self._webhook_secret = webhook_secret

    def create_checkout_session(
        self, *, customer_email: str, price_id: str, success_url: str, cancel_url: str, trial_days: int | None = None,
        metadata: dict | None = None,
    ) -> CheckoutSessionResult:
        kwargs: dict[str, Any] = dict(
            mode="subscription",
            customer_email=customer_email,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata or {},
        )
        if trial_days:
            kwargs["subscription_data"] = {"trial_period_days": trial_days}

        session = self._stripe.checkout.Session.create(**kwargs)
        return CheckoutSessionResult(session_id=session.id, checkout_url=session.url or "")

    def create_portal_session(self, *, stripe_customer_id: str, return_url: str) -> PortalSessionResult:
        session = self._stripe.billing_portal.Session.create(customer=stripe_customer_id, return_url=return_url)
        return PortalSessionResult(portal_url=session.url)

    def construct_webhook_event(self, *, payload: bytes, signature_header: str) -> dict[str, Any]:
        try:
            event = self._stripe.Webhook.construct_event(payload, signature_header, self._webhook_secret)
        except (ValueError, SignatureVerificationError) as e:
            raise StripeWebhookVerificationError(str(e)) from e
        return event

    def cancel_subscription(self, *, stripe_subscription_id: str, at_period_end: bool = True) -> None:
        if at_period_end:
            self._stripe.Subscription.modify(stripe_subscription_id, cancel_at_period_end=True)
        else:
            self._stripe.Subscription.delete(stripe_subscription_id)  # type: ignore[arg-type]


@dataclass
class FakeStripeClient:
    """
    Used in tests and local dev without real Stripe credentials. Checkout/portal
    URLs are fake-but-well-formed; construct_webhook_event skips signature
    verification entirely and just returns whatever event dict the test handed to
    enqueue_event(), which is the whole point -- tests construct exact subscription
    lifecycle payloads without needing a real Stripe signing key.
    """

    created_checkout_sessions: list[dict] = field(default_factory=list)
    created_portal_sessions: list[dict] = field(default_factory=list)
    canceled_subscriptions: list[dict] = field(default_factory=list)
    queued_webhook_events: list[dict] = field(default_factory=list)
    reject_signature: bool = False

    def create_checkout_session(
        self, *, customer_email: str, price_id: str, success_url: str, cancel_url: str, trial_days: int | None = None,
        metadata: dict | None = None,
    ) -> CheckoutSessionResult:
        session_id = f"cs_test_{uuid.uuid4().hex[:16]}"
        self.created_checkout_sessions.append(
            {"session_id": session_id, "customer_email": customer_email, "price_id": price_id, "trial_days": trial_days, "metadata": metadata}
        )
        return CheckoutSessionResult(session_id=session_id, checkout_url=f"https://checkout.stripe.example.com/{session_id}")

    def create_portal_session(self, *, stripe_customer_id: str, return_url: str) -> PortalSessionResult:
        self.created_portal_sessions.append({"stripe_customer_id": stripe_customer_id, "return_url": return_url})
        return PortalSessionResult(portal_url=f"https://billing.stripe.example.com/session/{uuid.uuid4().hex[:16]}")

    def construct_webhook_event(self, *, payload: bytes, signature_header: str) -> dict[str, Any]:
        if self.reject_signature:
            raise StripeWebhookVerificationError("Simulated invalid signature")
        if not self.queued_webhook_events:
            raise StripeWebhookVerificationError("No queued fake webhook event -- call queue_webhook_event() first in the test")
        return self.queued_webhook_events.pop(0)

    def queue_webhook_event(self, event: dict) -> None:
        self.queued_webhook_events.append(event)

    def cancel_subscription(self, *, stripe_subscription_id: str, at_period_end: bool = True) -> None:
        self.canceled_subscriptions.append({"stripe_subscription_id": stripe_subscription_id, "at_period_end": at_period_end})


@lru_cache
def get_stripe_client() -> StripeClient:
    from app.core.config import settings

    return RealStripeClient(api_key=settings.STRIPE_SECRET_KEY, webhook_secret=settings.STRIPE_WEBHOOK_SECRET)
