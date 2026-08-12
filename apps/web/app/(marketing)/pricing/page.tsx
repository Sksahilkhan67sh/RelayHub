import type { Metadata } from "next";
import { PricingClient } from "@/components/marketing/pricing-client";

export const metadata: Metadata = {
  title: "Pricing — RelayHub",
  description: "Simple, transparent pricing for RelayHub's webhook delivery platform. Free, Starter, Pro, and Enterprise plans -- every plan includes retries, replay, and a real dead-letter queue.",
  alternates: { canonical: "/pricing" },
  openGraph: { title: "Pricing — RelayHub", description: "Free, Starter, Pro, and Enterprise plans for webhook delivery infrastructure.", url: "/pricing" },
};

export default function PricingPage() {
  return <PricingClient />;
}
