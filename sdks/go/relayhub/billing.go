package relayhub

import "context"

type BillingService struct{ t *transport }

// ListPlans calls GET /v1/billing/plans -- Free, Starter, Pro, Enterprise. Public: no auth required.
func (s *BillingService) ListPlans(ctx context.Context, opts ...RequestOption) ([]Plan, error) {
	return decode[[]Plan](s.t.do(ctx, "GET", "/v1/billing/plans", nil, opts...))
}

// GetSubscription calls GET /v1/billing/subscription.
func (s *BillingService) GetSubscription(ctx context.Context, opts ...RequestOption) (Subscription, error) {
	return decode[Subscription](s.t.do(ctx, "GET", "/v1/billing/subscription", nil, opts...))
}

// GetUsage calls GET /v1/billing/usage -- deliveries used this billing period against the plan's limit.
func (s *BillingService) GetUsage(ctx context.Context, opts ...RequestOption) (Usage, error) {
	return decode[Usage](s.t.do(ctx, "GET", "/v1/billing/usage", nil, opts...))
}

// ListInvoices calls GET /v1/billing/invoices.
func (s *BillingService) ListInvoices(ctx context.Context, opts ...RequestOption) ([]Invoice, error) {
	return decode[[]Invoice](s.t.do(ctx, "GET", "/v1/billing/invoices", nil, opts...))
}

// CreateCheckoutSession calls POST /v1/billing/checkout -- returns a Stripe
// Checkout URL. Requires the "owner" role (not just "admin").
func (s *BillingService) CreateCheckoutSession(ctx context.Context, tier, successURL, cancelURL string, opts ...RequestOption) (CheckoutSession, error) {
	body := map[string]string{"tier": tier, "success_url": successURL, "cancel_url": cancelURL}
	return decode[CheckoutSession](s.t.do(ctx, "POST", "/v1/billing/checkout", body, opts...))
}

// CreatePortalSession calls POST /v1/billing/portal -- returns a Stripe
// customer portal URL. Requires the "owner" role.
func (s *BillingService) CreatePortalSession(ctx context.Context, returnURL string, opts ...RequestOption) (PortalSession, error) {
	body := map[string]string{"return_url": returnURL}
	return decode[PortalSession](s.t.do(ctx, "POST", "/v1/billing/portal", body, opts...))
}

// Note: POST /v1/billing/webhook (Stripe's inbound webhook receiver) is
// intentionally not wrapped here -- it's called by Stripe, never by an SDK consumer.
