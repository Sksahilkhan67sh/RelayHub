import type { Transport, RequestOptions } from "../transport.js";
import type { CheckoutSessionOut, InvoiceOut, PlanOut, PortalSessionOut, SubscriptionOut, UsageOut } from "../types.js";

export class BillingResource {
  constructor(private readonly transport: Transport) {}

  /** GET /v1/billing/plans -- Free, Starter, Pro, Enterprise. Public: no auth required. */
  listPlans(options?: RequestOptions) {
    return this.transport.request<PlanOut[]>("GET", "/v1/billing/plans", undefined, options);
  }

  /** GET /v1/billing/subscription */
  getSubscription(options?: RequestOptions) {
    return this.transport.request<SubscriptionOut>("GET", "/v1/billing/subscription", undefined, options);
  }

  /** GET /v1/billing/usage -- deliveries used this billing period against the plan's limit. */
  getUsage(options?: RequestOptions) {
    return this.transport.request<UsageOut>("GET", "/v1/billing/usage", undefined, options);
  }

  /** GET /v1/billing/invoices */
  listInvoices(options?: RequestOptions) {
    return this.transport.request<InvoiceOut[]>("GET", "/v1/billing/invoices", undefined, options);
  }

  /**
   * POST /v1/billing/checkout -- returns a Stripe Checkout URL to redirect the
   * user to. Requires the `owner` role (not just `admin`).
   */
  createCheckoutSession(params: { tier: "starter" | "pro" | "enterprise"; success_url: string; cancel_url: string }, options?: RequestOptions) {
    return this.transport.request<CheckoutSessionOut>("POST", "/v1/billing/checkout", params, options);
  }

  /**
   * POST /v1/billing/portal -- returns a Stripe customer portal URL for
   * self-service plan/payment management. Requires the `owner` role.
   */
  createPortalSession(params: { return_url: string }, options?: RequestOptions) {
    return this.transport.request<PortalSessionOut>("POST", "/v1/billing/portal", params, options);
  }

  // Note: POST /v1/billing/webhook (Stripe's inbound webhook receiver) is
  // intentionally not wrapped here -- it's called by Stripe, never by an SDK consumer.
}
