from __future__ import annotations

from ..http import RequestOptions, Transport
from ..types import CheckoutSessionOut, InvoiceOut, PlanOut, PortalSessionOut, SubscriptionOut, UsageOut


class BillingResource:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def list_plans(self, options: RequestOptions | None = None) -> list[PlanOut]:
        """GET /v1/billing/plans -- Free, Starter, Pro, Enterprise. Public: no auth required."""
        return self._transport.request("GET", "/v1/billing/plans", None, options)

    def get_subscription(self, options: RequestOptions | None = None) -> SubscriptionOut:
        """GET /v1/billing/subscription"""
        return self._transport.request("GET", "/v1/billing/subscription", None, options)

    def get_usage(self, options: RequestOptions | None = None) -> UsageOut:
        """GET /v1/billing/usage -- deliveries used this billing period against the plan's limit."""
        return self._transport.request("GET", "/v1/billing/usage", None, options)

    def list_invoices(self, options: RequestOptions | None = None) -> list[InvoiceOut]:
        """GET /v1/billing/invoices"""
        return self._transport.request("GET", "/v1/billing/invoices", None, options)

    def create_checkout_session(
        self, *, tier: str, success_url: str, cancel_url: str, options: RequestOptions | None = None
    ) -> CheckoutSessionOut:
        """POST /v1/billing/checkout -- returns a Stripe Checkout URL. Requires the 'owner' role (not just 'admin')."""
        body = {"tier": tier, "success_url": success_url, "cancel_url": cancel_url}
        return self._transport.request("POST", "/v1/billing/checkout", body, options)

    def create_portal_session(self, *, return_url: str, options: RequestOptions | None = None) -> PortalSessionOut:
        """POST /v1/billing/portal -- returns a Stripe customer portal URL. Requires the 'owner' role."""
        return self._transport.request("POST", "/v1/billing/portal", {"return_url": return_url}, options)

    # Note: POST /v1/billing/webhook (Stripe's inbound webhook receiver) is
    # intentionally not wrapped here -- it's called by Stripe, never by an SDK consumer.
