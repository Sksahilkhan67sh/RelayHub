import type { Metadata } from "next";
import { ShieldCheck, GitBranch, Layers, Compass } from "lucide-react";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";

export const metadata: Metadata = {
  title: "About — RelayHub",
  description: "RelayHub's mission, architecture philosophy, and approach to security and engineering.",
  alternates: { canonical: "/about" },
  openGraph: { title: "About — RelayHub", description: "Why RelayHub exists and how it's built.", url: "/about" },
};

export default function AboutPage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <div className="max-w-2xl">
          <Eyebrow>About</Eyebrow>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">
            Webhooks are infrastructure. We build them like it.
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Most products treat outbound webhooks as an afterthought: a single HTTP call, fired and forgotten. RelayHub
            exists because the moment a partner integration depends on that call landing, &ldquo;fired and forgotten&rdquo; isn&apos;t
            good enough anymore.
          </p>
        </div>
      </Section>

      <Section className="pt-0">
        <div className="grid gap-10 sm:grid-cols-2">
          <div>
            <SectionHeading title="Mission" />
            <p className="mt-4 text-[13.5px] leading-relaxed text-graphite-600 dark:text-graphite-400">
              Make it so no engineering team has to build a retry queue, a dead-letter table, and a delivery log explorer
              from scratch just to send webhooks reliably. That work is well understood and worth doing once, correctly,
              so every team building an event-driven product can start from a solid floor instead of rebuilding it.
            </p>
          </div>
          <div>
            <SectionHeading title="Vision" />
            <p className="mt-4 text-[13.5px] leading-relaxed text-graphite-600 dark:text-graphite-400">
              A world where &ldquo;did the webhook actually arrive?&rdquo; is never a question your support team has to answer by
              guessing. Every delivery attempt should be visible, explainable, and replayable -- not a black box between
              your event and your partner&apos;s endpoint.
            </p>
          </div>
        </div>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-20">
          <SectionHeading eyebrow="How we build" title="Architecture philosophy" />
          <div className="mt-10 grid gap-8 sm:grid-cols-2">
            <div className="flex gap-4">
              <Layers className="h-5 w-5 shrink-0 text-signal-amber" />
              <div>
                <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Delivery is asynchronous, on purpose</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
                  Publishing an event and delivering it are separate concerns, running on separate paths. A slow or down
                  endpoint on your side never slows down your API calls to RelayHub.
                </p>
              </div>
            </div>
            <div className="flex gap-4">
              <ShieldCheck className="h-5 w-5 shrink-0 text-signal-amber" />
              <div>
                <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Tenant isolation at the query layer</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
                  Every database query is scoped by organization in the data-access layer itself, not left to individual
                  route handlers to remember. Isolation is structural, not a convention people can forget to follow.
                </p>
              </div>
            </div>
            <div className="flex gap-4">
              <GitBranch className="h-5 w-5 shrink-0 text-signal-amber" />
              <div>
                <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Failure is a first-class state</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
                  Retries, dead-lettering, and replay aren&apos;t bolted on after the fact -- they&apos;re modeled into the
                  delivery pipeline from the start, the same way success is.
                </p>
              </div>
            </div>
            <div className="flex gap-4">
              <Compass className="h-5 w-5 shrink-0 text-signal-amber" />
              <div>
                <h3 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Boring, observable technology</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-graphite-600 dark:text-graphite-400">
                  Every delivery attempt is logged with enough detail to answer &ldquo;what happened?&rdquo; without needing to ask us.
                  We&apos;d rather ship something explainable than something clever.
                </p>
              </div>
            </div>
          </div>
        </Section>
      </div>

      <Section>
        <SectionHeading eyebrow="Security" title="Security is load-bearing, not a checkbox" />
        <p className="mt-4 max-w-2xl text-[13.5px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Every delivery is signed with a per-endpoint secret. Signing secrets and API keys are hashed before they ever
          touch the database -- the same as your account password. Password-reset and invitation tokens are one-time-use
          and expire automatically. Role-based access control and audit logging are built into the platform, not an
          enterprise add-on bolted on afterward. See <a href="/features#security" className="text-signal-amber hover:underline">Security on the Features page</a> for the full list.
        </p>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-20">
          <SectionHeading eyebrow="Open source" title="What's open, what isn't" />
          <p className="mt-4 max-w-2xl text-[13.5px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            RelayHub the hosted platform is closed source today. We publish our signature-verification snippets and API
            documentation openly so you&apos;re never locked into a proprietary client just to verify a webhook -- see the{" "}
            <a href="/docs#webhooks" className="text-signal-amber hover:underline">Webhooks docs</a>. Whether more of the
            platform opens up over time is an active conversation internally, not a promise we&apos;re making today.
          </p>
        </Section>
      </div>

      <Section>
        <SectionHeading eyebrow="Engineering" title="How the team works" />
        <p className="mt-4 max-w-2xl text-[13.5px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Small team, high ownership. Whoever builds a feature owns its production behavior -- including the on-call
          rotation for it. We write tests for the failure paths before we write them for the happy path, because the
          failure paths are the entire point of this product.
        </p>
      </Section>

      <div className="border-t border-graphite-100 bg-graphite-50 dark:border-graphite-800 dark:bg-graphite-900/40">
        <Section className="py-20">
          <SectionHeading eyebrow="Roadmap" title="What's next" description="See the full, dated history of what's shipped on the Changelog." />
          <ul className="mt-8 flex flex-col gap-3">
            {["Typed SDKs for Node.js and Python", "A command-line tool for tailing delivery logs", "An AI copilot for diagnosing failing deliveries", "Single sign-on for Enterprise organizations"].map((item) => (
              <li key={item} className="flex items-center gap-2.5 text-[13.5px] text-graphite-700 dark:text-graphite-300">
                <span className="h-1.5 w-1.5 rounded-full bg-signal-amber" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      </div>
    </>
  );
}
