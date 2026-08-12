# Billing -- `/billing`

Source: `backend/app/modules/billing/routes.py`

Billing is Stripe-backed. `POST /billing/checkout` and `POST /billing/portal`
redirect through Stripe-hosted pages; RelayHub never handles card details
directly.

## GET /billing/plans

- **Auth:** none -- public
- **Response `200`:** `PlanOut[]` -- Free, Starter, Pro, Enterprise. Each entry includes `price_cents`, `max_deliveries_per_month`, `max_endpoints`, `log_retention_days`, per-window rate limits, and feature flags (`has_advanced_analytics`, `has_priority_support`, `has_sso`, `allow_overage`).

## GET /billing/subscription

- **Auth:** Bearer access token
- **RBAC:** any role
- **Response `200`:** `SubscriptionOut` -- `{ "id", "plan", "status", "current_period_start", "current_period_end", "trial_end", "cancel_at_period_end" }`

## GET /billing/usage

- **RBAC:** any role
- **Response `200`:** `UsageOut` -- `{ "period_start", "period_end", "delivery_count", "max_deliveries_per_month", "percent_used", "endpoint_count", "max_endpoints" }`

## GET /billing/invoices

- **RBAC:** any role
- **Response `200`:** `InvoiceOut[]`

## POST /billing/checkout

- **RBAC:** `owner` (not `admin` -- billing changes require ownership)
- **Body:** `{ "tier": "starter"|"pro"|"enterprise", "success_url": string, "cancel_url": string }`
- **Response `200`:** `{ "checkout_url": string }` -- redirect the user here

```bash
curl -X POST https://api.relayhub.dev/v1/billing/checkout \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"tier":"pro","success_url":"https://app.example.com/billing?success=1","cancel_url":"https://app.example.com/billing"}'
```

## POST /billing/portal

- **RBAC:** `owner`
- **Body:** `{ "return_url": string }`
- **Response `200`:** `{ "portal_url": string }` -- Stripe customer portal for self-service plan/payment management

## POST /billing/webhook

Stripe's inbound webhook receiver -- called by Stripe, never by an API consumer
or SDK. Verifies the Stripe signature header before processing.

- **Auth:** Stripe webhook signature (not a RelayHub bearer token)
