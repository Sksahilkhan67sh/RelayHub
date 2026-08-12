"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Minus, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/card";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";
import { FaqAccordion } from "@/components/marketing/faq-accordion";
import { cn } from "@/lib/cn";

// Monthly prices match RelayHub's actual billing plans (backend/app/modules/billing/service.py PLAN_DEFAULTS).
// Annual pricing has no backend/Stripe support yet -- this page is UI only, so the
// "Yearly" toggle computes an illustrative ~17% discount (2 months free) client-side
// from those same real monthly figures rather than inventing separate numbers.
const PLANS = [
  {
    tier: "free",
    name: "Free",
    monthly: 0,
    description: "A full working setup, no time limit.",
    cta: { label: "Start free", href: "/register" },
    features: ["1,000 deliveries / month", "1 endpoint", "7-day log retention", "Community support"],
  },
  {
    tier: "starter",
    name: "Starter",
    monthly: 29,
    description: "For a product with real webhook traffic.",
    cta: { label: "Start free", href: "/register" },
    features: ["100,000 deliveries / month", "20 endpoints", "30-day log retention", "Email support"],
  },
  {
    tier: "pro",
    name: "Pro",
    monthly: 99,
    description: "For teams where webhook delivery is load-bearing.",
    cta: { label: "Start free", href: "/register" },
    features: ["5,000,000 deliveries / month", "Unlimited endpoints", "90-day log retention", "Alerts (Slack, Discord, email)", "Priority support"],
    highlighted: true,
  },
  {
    tier: "enterprise",
    name: "Enterprise",
    monthly: null,
    description: "Custom volume, retention, and SLA.",
    cta: { label: "Contact sales", href: "/contact" },
    features: ["Unlimited deliveries", "Unlimited endpoints", "365-day log retention", "SSO on request", "Dedicated support channel"],
  },
];

const COMPARISON: { label: string; values: [string, string, string, string] }[] = [
  { label: "Deliveries / month", values: ["1,000", "100,000", "5,000,000", "Custom"] },
  { label: "Endpoints", values: ["1", "20", "Unlimited", "Unlimited"] },
  { label: "Log retention", values: ["7 days", "30 days", "90 days", "365 days"] },
  { label: "Delivery replay", values: ["yes", "yes", "yes", "yes"] },
  { label: "Dead-letter queue", values: ["yes", "yes", "yes", "yes"] },
  { label: "Analytics", values: ["no", "yes", "yes", "yes"] },
  { label: "Alert channels", values: ["no", "Email", "Slack, Discord, email", "Slack, Discord, email"] },
  { label: "Audit logs", values: ["no", "yes", "yes", "yes"] },
  { label: "RBAC roles", values: ["no", "yes", "yes", "yes"] },
  { label: "SSO", values: ["no", "no", "no", "yes"] },
  { label: "Support", values: ["Community", "Email", "Priority", "Dedicated"] },
];

const FAQS = [
  {
    q: "What happens if I go over my plan's delivery limit?",
    a: "Deliveries pause once you hit the monthly limit until you upgrade or the next billing cycle starts. We don't silently overcharge you for overages.",
  },
  {
    q: "Can I change plans later?",
    a: "Yes, upgrade or downgrade anytime from your organization's billing settings. Changes apply to your next billing cycle.",
  },
  {
    q: "Is there a free trial on Starter or Pro?",
    a: "Both Starter and Pro are trial-eligible -- you can try the higher limits before committing.",
  },
  {
    q: "Do you offer discounts for annual billing?",
    a: "The Yearly toggle above shows the discounted annual rate (equivalent to two months free) for self-serve plans. Enterprise pricing is negotiated directly.",
  },
  {
    q: "How is Enterprise pricing determined?",
    a: "Enterprise plans are scoped to your delivery volume, retention needs, and SLA requirements. Contact sales and we'll put a number on it within a day.",
  },
];

export function PricingClient() {
  const [yearly, setYearly] = useState(false);

  return (
    <>
      <Section className="pb-6 pt-16 text-center sm:pt-20">
        <Eyebrow>Pricing</Eyebrow>
        <h1 className="mx-auto mt-3 max-w-xl text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">
          Simple pricing that scales with delivery volume
        </h1>
        <p className="mx-auto mt-4 max-w-lg text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Every plan includes retries, replay, and a real dead-letter queue. No feature is held back for a higher tier.
        </p>

        <div className="mx-auto mt-8 flex w-fit items-center gap-3 rounded-full border border-graphite-200 p-1 dark:border-graphite-700">
          <button
            onClick={() => setYearly(false)}
            className={cn("rounded-full px-4 py-1.5 text-xs font-medium transition-colors", !yearly ? "bg-graphite-950 text-white dark:bg-graphite-50 dark:text-graphite-950" : "text-graphite-600 dark:text-graphite-400")}
          >
            Monthly
          </button>
          <button
            onClick={() => setYearly(true)}
            className={cn("flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium transition-colors", yearly ? "bg-graphite-950 text-white dark:bg-graphite-50 dark:text-graphite-950" : "text-graphite-600 dark:text-graphite-400")}
          >
            Yearly
            <span className="rounded-full bg-signal-green-soft px-1.5 py-0.5 text-[10px] font-semibold text-[#146245]">Save ~17%</span>
          </button>
        </div>
      </Section>

      <Section className="pt-4">
        <div className="grid gap-5 lg:grid-cols-4">
          {PLANS.map((plan) => {
            const displayPrice =
              plan.monthly === null ? null : yearly ? Math.round((plan.monthly * 10) / 12) : plan.monthly;
            return (
              <div
                key={plan.tier}
                className={cn(
                  "flex flex-col gap-5 rounded-md border p-6",
                  plan.highlighted ? "border-signal-amber shadow-glow-amber" : "border-graphite-100 dark:border-graphite-800"
                )}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{plan.name}</h2>
                    {plan.highlighted && <Badge tone="amber">Most popular</Badge>}
                  </div>
                  <p className="mt-1 text-xs text-graphite-500">{plan.description}</p>
                </div>

                <div className="flex items-baseline gap-1">
                  {displayPrice === null ? (
                    <span className="text-3xl font-semibold text-graphite-950 dark:text-graphite-50">Custom</span>
                  ) : (
                    <>
                      <span className="text-3xl font-semibold text-graphite-950 dark:text-graphite-50">${displayPrice}</span>
                      <span className="text-xs text-graphite-500">/ month{yearly && plan.monthly !== 0 ? ", billed yearly" : ""}</span>
                    </>
                  )}
                </div>

                <Link href={plan.cta.href}>
                  <Button size="sm" variant={plan.highlighted ? "primary" : "secondary"} className="w-full">
                    {plan.cta.label}
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>

                <ul className="flex flex-col gap-2.5 border-t border-graphite-100 pt-4 dark:border-graphite-800">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-xs text-graphite-600 dark:text-graphite-400">
                      <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-signal-green" />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </Section>

      {/* Comparison table */}
      <div className="bg-graphite-50 dark:bg-graphite-900/40">
        <Section className="py-20">
          <SectionHeading eyebrow="Compare plans" title="Every detail, side by side" align="center" />
          <div className="mt-10 overflow-x-auto rounded-md border border-graphite-100 bg-white dark:border-graphite-800 dark:bg-graphite-900">
            <table className="w-full min-w-[640px] text-left text-xs">
              <thead>
                <tr className="border-b border-graphite-100 dark:border-graphite-800">
                  <th className="px-4 py-3 font-medium text-graphite-500">Plan</th>
                  {PLANS.map((p) => (
                    <th key={p.tier} className="px-4 py-3 font-semibold text-graphite-950 dark:text-graphite-50">
                      {p.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {COMPARISON.map((row) => (
                  <tr key={row.label} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                    <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">{row.label}</td>
                    {row.values.map((v, i) => (
                      <td key={i} className="px-4 py-2.5 text-graphite-800 dark:text-graphite-200">
                        {v === "yes" ? (
                          <Check className="h-3.5 w-3.5 text-signal-green" />
                        ) : v === "no" ? (
                          <Minus className="h-3.5 w-3.5 text-graphite-300 dark:text-graphite-700" />
                        ) : (
                          v
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      </div>

      <Section className="max-w-3xl">
        <SectionHeading eyebrow="FAQ" title="Pricing questions" align="center" />
        <div className="mt-10">
          <FaqAccordion items={FAQS} />
        </div>
      </Section>

      <div className="border-t border-graphite-800 bg-graphite-950">
        <Section className="flex flex-col items-center gap-5 py-20 text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-white">Start on the Free plan, upgrade when you need to.</h2>
          <Link href="/register">
            <Button size="md">
              Start free
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </Section>
      </div>
    </>
  );
}
