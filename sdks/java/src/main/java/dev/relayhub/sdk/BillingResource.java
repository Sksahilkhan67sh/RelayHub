package dev.relayhub.sdk;

import java.util.List;
import java.util.Map;

public final class BillingResource {
    private final Transport transport;

    BillingResource(Transport transport) { this.transport = transport; }

    /** GET /v1/billing/plans -- Free, Starter, Pro, Enterprise. Public: no auth required. */
    public List<Models.Plan> listPlans() { return listPlans(null); }
    public List<Models.Plan> listPlans(RequestOptions options) {
        return transport.requestList("GET", "/v1/billing/plans", null, Models.Plan.class, options);
    }

    /** GET /v1/billing/subscription */
    public Models.Subscription getSubscription() { return getSubscription(null); }
    public Models.Subscription getSubscription(RequestOptions options) {
        return transport.request("GET", "/v1/billing/subscription", null, Models.Subscription.class, options);
    }

    /** GET /v1/billing/usage -- deliveries used this billing period against the plan's limit. */
    public Models.Usage getUsage() { return getUsage(null); }
    public Models.Usage getUsage(RequestOptions options) {
        return transport.request("GET", "/v1/billing/usage", null, Models.Usage.class, options);
    }

    /** GET /v1/billing/invoices */
    public List<Models.Invoice> listInvoices() { return listInvoices(null); }
    public List<Models.Invoice> listInvoices(RequestOptions options) {
        return transport.requestList("GET", "/v1/billing/invoices", null, Models.Invoice.class, options);
    }

    /** POST /v1/billing/checkout -- returns a Stripe Checkout URL. Requires the "owner" role (not just "admin"). */
    public Models.CheckoutSession createCheckoutSession(String tier, String successUrl, String cancelUrl) { return createCheckoutSession(tier, successUrl, cancelUrl, null); }
    public Models.CheckoutSession createCheckoutSession(String tier, String successUrl, String cancelUrl, RequestOptions options) {
        return transport.request("POST", "/v1/billing/checkout", Map.of("tier", tier, "success_url", successUrl, "cancel_url", cancelUrl), Models.CheckoutSession.class, options);
    }

    /** POST /v1/billing/portal -- returns a Stripe customer portal URL. Requires the "owner" role. */
    public Models.PortalSession createPortalSession(String returnUrl) { return createPortalSession(returnUrl, null); }
    public Models.PortalSession createPortalSession(String returnUrl, RequestOptions options) {
        return transport.request("POST", "/v1/billing/portal", Map.of("return_url", returnUrl), Models.PortalSession.class, options);
    }

    // Note: POST /v1/billing/webhook (Stripe's inbound webhook receiver) is
    // intentionally not wrapped here -- it's called by Stripe, never by an SDK consumer.
}
