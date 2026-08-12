"use client";

import { useEffect, useState } from "react";
import { CreditCard, ExternalLink, Check } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { SubscriptionOut, PlanOut, InvoiceOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardBody, Badge } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";

export default function BillingPage() {
  const [subscription, setSubscription] = useState<SubscriptionOut | null>(null);
  const [plans, setPlans] = useState<PlanOut[] | null>(null);
  const [invoices, setInvoices] = useState<InvoiceOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyTier, setBusyTier] = useState<string | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);

  async function load() {
    try {
      const [sub, planList, invoiceList] = await Promise.all([
        api.get<SubscriptionOut>("/v1/billing/subscription"),
        api.get<PlanOut[]>("/v1/billing/plans"),
        api.get<InvoiceOut[]>("/v1/billing/invoices"),
      ]);
      setSubscription(sub);
      setPlans(planList);
      setInvoices(invoiceList);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load billing information");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleUpgrade(tier: string) {
    setBusyTier(tier);
    try {
      const result = await api.post<{ checkout_url: string }>("/v1/billing/checkout", {
        tier,
        success_url: `${window.location.origin}/billing?checkout=success`,
        cancel_url: `${window.location.origin}/billing?checkout=cancelled`,
      });
      window.location.href = result.checkout_url;
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to start checkout");
      setBusyTier(null);
    }
  }

  async function handlePortal() {
    setPortalLoading(true);
    try {
      const result = await api.post<{ portal_url: string }>("/v1/billing/portal", {
        return_url: `${window.location.origin}/billing`,
      });
      window.location.href = result.portal_url;
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Failed to open billing portal");
      setPortalLoading(false);
    }
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <StatusDot color="red" size="md" />
        <p className="text-xs text-graphite-600 dark:text-graphite-400">{error}</p>
      </div>
    );
  }

  if (!subscription || !plans) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Billing</h1>
          <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">Manage your plan and payment method.</p>
        </div>
        {subscription.plan.tier !== "free" && (
          <Button size="sm" variant="secondary" onClick={handlePortal} loading={portalLoading}>
            <ExternalLink className="h-3.5 w-3.5" />
            Manage in Stripe
          </Button>
        )}
      </div>

      <Card>
        <CardBody className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{subscription.plan.name} plan</span>
              <StatusDot color={statusToSignalColor(subscription.status)} label={subscription.status} />
            </div>
            {subscription.current_period_end && (
              <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
                Renews {new Date(subscription.current_period_end).toLocaleDateString()}
                {subscription.cancel_at_period_end && " (cancels at period end)"}
              </p>
            )}
          </div>
          <span className="tabular text-lg font-semibold text-graphite-950 dark:text-graphite-50">
            ${(subscription.plan.price_cents / 100).toFixed(0)}
            <span className="text-xs font-normal text-graphite-500">/mo</span>
          </span>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {plans.map((plan) => (
          <PlanCard
            key={plan.tier}
            plan={plan}
            isCurrent={plan.tier === subscription.plan.tier}
            onUpgrade={() => handleUpgrade(plan.tier)}
            loading={busyTier === plan.tier}
          />
        ))}
      </div>

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Invoice history</h2>
        </CardHeader>
        <CardBody className="p-0">
          {!invoices || invoices.length === 0 ? (
            <EmptyState icon={CreditCard} title="No invoices yet" description="Invoices will appear here once you're on a paid plan." />
          ) : (
            <table className="w-full text-left text-xs">
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                    <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                      {new Date(inv.created_at).toLocaleDateString()}
                    </td>
                    <td className="tabular px-4 py-2.5 font-medium text-graphite-950 dark:text-graphite-50">
                      ${(inv.amount_cents / 100).toFixed(2)}
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge tone={inv.status === "paid" ? "green" : "amber"}>{inv.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function PlanCard({
  plan,
  isCurrent,
  onUpgrade,
  loading,
}: {
  plan: PlanOut;
  isCurrent: boolean;
  onUpgrade: () => void;
  loading: boolean;
}) {
  const canCheckout = plan.tier === "starter" || plan.tier === "pro";

  return (
    <Card className={isCurrent ? "border-signal-amber" : ""}>
      <CardBody className="flex flex-col gap-3">
        <div>
          <span className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{plan.name}</span>
          <div className="tabular mt-0.5 text-lg font-semibold text-graphite-950 dark:text-graphite-50">
            ${(plan.price_cents / 100).toFixed(0)}
            <span className="text-xs font-normal text-graphite-500">/mo</span>
          </div>
        </div>
        <ul className="flex flex-col gap-1 text-xs text-graphite-600 dark:text-graphite-400">
          <FeatureLine text={`${plan.max_deliveries_per_month?.toLocaleString() ?? "Unlimited"} deliveries/mo`} />
          <FeatureLine text={`${plan.max_endpoints ?? "Unlimited"} endpoints`} />
          <FeatureLine text={`${plan.log_retention_days}-day log retention`} />
          {plan.has_priority_support && <FeatureLine text="Priority support" />}
          {plan.has_advanced_analytics && <FeatureLine text="Advanced analytics" />}
          {plan.has_sso && <FeatureLine text="SSO" />}
        </ul>
        {isCurrent ? (
          <Badge tone="neutral">Current plan</Badge>
        ) : canCheckout ? (
          <Button size="sm" variant="secondary" onClick={onUpgrade} loading={loading}>
            {plan.price_cents === 0 ? "Downgrade" : "Upgrade"}
          </Button>
        ) : (
          <span className="text-xs text-graphite-500">{plan.tier === "enterprise" ? "Contact sales" : "—"}</span>
        )}
      </CardBody>
    </Card>
  );
}

function FeatureLine({ text }: { text: string }) {
  return (
    <li className="flex items-center gap-1.5">
      <Check className="h-3 w-3 text-signal-green" />
      {text}
    </li>
  );
}
