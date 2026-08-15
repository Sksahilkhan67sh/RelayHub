import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/card";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";
import type { JobPostingOut } from "@/lib/types";

export const metadata: Metadata = {
  title: "Careers — RelayHub",
  description: "Open positions at RelayHub, our culture, benefits, and hiring process.",
  alternates: { canonical: "/careers" },
  openGraph: { title: "Careers — RelayHub", description: "Join the team building webhook delivery infrastructure.", url: "/careers" },
};

// Open positions are admin-managed (create/edit/deactivate via /admin/careers), so
// they're fetched per-request rather than hardcoded, unlike the Benefits/Culture/
// Hiring-process sections below, which are static company-policy copy, not
// individually postable listings.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getOpenPositions(): Promise<JobPostingOut[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/v1/content/job-postings`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return []; // marketing page should still render even if the API is briefly unreachable
  }
}

const BENEFITS = [
  { title: "Remote-first", body: "Work from anywhere within a few hours of US or EU business hours. No office to relocate for." },
  { title: "Unlimited PTO, real minimums", body: "No cap on time off, and a four-week minimum we actually enforce." },
  { title: "Health coverage", body: "Medical, dental, and vision covered for you, with a contribution toward dependents." },
  { title: "Home office budget", body: "A one-time setup budget plus an annual refresh for your desk, monitor, and chair." },
  { title: "Learning budget", body: "An annual budget for courses, books, or conferences -- no approval theater." },
  { title: "Equity", body: "Every full-time hire gets equity, not just early employees." },
];

const HIRING_STEPS = [
  { title: "Application review", body: "We read every application. If it's a fit, you'll hear back within a week either way." },
  { title: "Intro call", body: "30 minutes with the hiring manager -- about the role, about you, no trick questions." },
  { title: "Technical conversation", body: "A conversation about real problems we've solved (or are solving), not a whiteboard algorithm quiz." },
  { title: "Team interviews", body: "Two or three conversations with people you'd actually work with." },
  { title: "Offer", body: "If it's a match on both sides, we move fast -- usually within a few days of the final interview." },
];

export default async function CareersPage() {
  const openPositions = await getOpenPositions();

  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <div className="max-w-2xl">
          <Eyebrow>Careers</Eyebrow>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">Help build the infrastructure other teams depend on</h1>
          <p className="mt-4 text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            We&apos;re a small, remote-first team. Every hire has real ownership over what they build -- including being on
            the hook when it breaks at 2am.
          </p>
        </div>
      </Section>

      <Section className="pt-0">
        <SectionHeading eyebrow="Open positions" title="Where we're hiring" />
        {openPositions.length === 0 ? (
          <p className="mt-8 text-sm text-graphite-500">No open positions right now -- check back soon.</p>
        ) : (
          <div className="mt-8 flex flex-col divide-y divide-graphite-100 border-y border-graphite-100 dark:divide-graphite-800 dark:border-graphite-800">
            {openPositions.map((p) => (
              <Link
                key={p.id}
                href="/contact"
                className="flex flex-col items-start justify-between gap-2 py-4 sm:flex-row sm:items-center"
              >
                <div>
                  <h3 className="text-sm font-medium text-graphite-950 dark:text-graphite-50">{p.title}</h3>
                  <div className="mt-1 flex items-center gap-3 text-xs text-graphite-500">
                    <Badge tone="neutral">{p.team}</Badge>
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      {p.location}
                    </span>
                  </div>
                </div>
                <span className="flex items-center gap-1 text-xs font-medium text-signal-amber">
                  Apply <ArrowRight className="h-3 w-3" />
                </span>
              </Link>
            ))}
          </div>
        )}
        <p className="mt-4 text-xs text-graphite-500">
          Don&apos;t see a fit but think you should be here anyway?{" "}
          <Link href="/contact" className="text-signal-amber hover:underline">Reach out</Link> -- we read every message.
        </p>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-20">
          <SectionHeading eyebrow="Culture" title="How we work" />
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            <p className="text-[13.5px] leading-relaxed text-graphite-600 dark:text-graphite-400">
              Small team, high trust, few meetings. Most collaboration happens async and in writing, because a written
              decision is one the next person can actually find later.
            </p>
            <p className="text-[13.5px] leading-relaxed text-graphite-600 dark:text-graphite-400">
              We ship in small increments and put real thought into failure paths before we call something done. If a
              feature doesn&apos;t have a plan for what happens when it breaks, it isn&apos;t finished.
            </p>
          </div>
        </Section>
      </div>

      <Section>
        <SectionHeading eyebrow="Benefits" title="What you get" />
        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {BENEFITS.map((b) => (
            <div key={b.title} className="rounded-md border border-graphite-100 p-5 dark:border-graphite-800">
              <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{b.title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">{b.body}</p>
            </div>
          ))}
        </div>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-20">
          <SectionHeading eyebrow="Hiring process" title="What to expect" />
          <div className="mt-10 flex flex-col gap-6">
            {HIRING_STEPS.map((step, i) => (
              <div key={step.title} className="flex gap-4">
                <span className="font-mono text-xs text-signal-amber">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{step.title}</h3>
                  <p className="mt-1 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">{step.body}</p>
                </div>
              </div>
            ))}
          </div>
        </Section>
      </div>

      <Section className="flex flex-col items-center gap-4 text-center">
        <h2 className="text-2xl font-semibold tracking-tight text-graphite-950 dark:text-graphite-50">Have questions before applying?</h2>
        <Link href="/contact">
          <Button size="md">
            Contact us
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </Link>
      </Section>
    </>
  );
}
