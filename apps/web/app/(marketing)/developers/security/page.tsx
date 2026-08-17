import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ShieldCheck, KeyRound, Globe, Gauge, FileSignature, Building2 } from "lucide-react";
import { Section, SectionHeading, Eyebrow } from "@/components/marketing/section";

export const metadata: Metadata = {
  title: "Security — RelayHub Developers",
  description: "RelayHub's real security architecture: authentication, webhook signatures, SSRF protection for destination URLs, rate limiting, tenant isolation, and response headers.",
  alternates: { canonical: "/developers/security" },
  openGraph: {
    title: "RelayHub Security",
    description: "Authentication, signing, SSRF protection, rate limiting, and tenant isolation, as actually implemented.",
    url: "/developers/security",
    type: "article",
  },
};

export default function SecurityPage() {
  return (
    <>
      <Section className="pb-8 pt-16 sm:pt-20">
        <Link href="/developers" className="flex w-fit items-center gap-1 text-xs text-graphite-500 hover:text-graphite-950 dark:hover:text-graphite-50">
          <ArrowLeft className="h-3.5 w-3.5" />
          Developers
        </Link>
        <Eyebrow>Security</Eyebrow>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">
          Security architecture
        </h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Every mechanism below is described exactly as it&apos;s implemented -- including the parts that are
          deliberately incomplete on one side and reinforced on another.
        </p>
      </Section>

      <Section className="flex flex-col gap-12 pb-24">
        <div id="authentication" className="scroll-mt-20">
          <div className="flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-signal-amber" />
            <h2 className="text-lg font-semibold text-graphite-950 dark:text-graphite-50">Authentication</h2>
          </div>
          <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Two separate mechanisms, not interchangeable. Dashboard sessions use a JWT in{" "}
            <code>Authorization: Bearer $TOKEN</code>, issued by <code>/v1/auth/login</code> and refreshed via{" "}
            <code>/v1/auth/refresh</code>. Programmatic API access uses a scoped key in its own{" "}
            <code>X-RelayHub-Api-Key</code> header -- sending it as <code>Authorization</code> instead (an easy
            mistake; every RelayHub SDK made exactly this mistake until a recent fix) will 401.
          </p>
          <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Keys are environment-bound (<code>test</code> or <code>live</code>) and shown in full exactly once, at
            creation. A revoked key stops authenticating immediately -- there is no grace period.
          </p>
        </div>

        <div id="signatures" className="scroll-mt-20">
          <div className="flex items-center gap-2">
            <FileSignature className="h-4 w-4 text-signal-amber" />
            <h2 className="text-lg font-semibold text-graphite-950 dark:text-graphite-50">Webhook signatures</h2>
          </div>
          <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Every delivery is signed with HMAC-SHA256 over <code>{"<timestamp>.<nonce>."}</code> concatenated with
            the raw request body -- not the body alone. Signing the timestamp and nonce is what makes a captured
            request unusable later: replaying it produces a signature that won&apos;t match unless the timestamp and
            nonce are replayed identically too, and your own verification code should reject stale timestamps.
          </p>
          <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Four headers arrive with every delivery: <code>X-RelayHub-Signature</code>, <code>X-RelayHub-Timestamp</code>,{" "}
            <code>X-RelayHub-Nonce</code>, and <code>X-RelayHub-Event</code> / <code>X-RelayHub-Delivery-ID</code> for
            routing. See the{" "}
            <Link href="/developers/quickstart#verify" className="text-signal-amber hover:underline">
              Quickstart&apos;s verification example
            </Link>{" "}
            for real, tested code.
          </p>
        </div>

        <div id="ssrf" className="scroll-mt-20">
          <div className="flex items-center gap-2">
            <Globe className="h-4 w-4 text-signal-amber" />
            <h2 className="text-lg font-semibold text-graphite-950 dark:text-graphite-50">SSRF protection for destination URLs</h2>
          </div>
          <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Registering an endpoint runs synchronous checks: <code>https://</code> is required in production,
            literal loopback/private/link-local/reserved IPs are rejected outright, and{" "}
            <code>localhost</code>, <code>localhost.localdomain</code>, <code>metadata.google.internal</code>, and
            any <code>.local</code> hostname are blocked by name.
          </p>
          <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            That registration-time check alone can&apos;t catch DNS rebinding -- a hostname that resolves to a safe
            IP at registration but a different (internal) IP later. RelayHub&apos;s own source is explicit about this:
            registration-time validation is a fast first layer, not a substitute for re-resolving and re-validating
            the destination immediately before each actual delivery attempt, which is where the real protection
            against rebinding lives.
          </p>
        </div>

        <div id="rate-limiting" className="scroll-mt-20">
          <div className="flex items-center gap-2">
            <Gauge className="h-4 w-4 text-signal-amber" />
            <h2 className="text-lg font-semibold text-graphite-950 dark:text-graphite-50">Rate limiting</h2>
          </div>
          <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Three tiers per API key, enforced together: 100/minute, 1,000/hour, 10,000/day by default (your plan can
            raise the hour/day tiers; the per-minute tier can also be overridden per key). Every response carries{" "}
            <code>X-RateLimit-Limit-*</code>, <code>X-RateLimit-Remaining-*</code>, and{" "}
            <code>X-RateLimit-Reset-*</code> headers for each tier. Exceeding any tier returns{" "}
            <code>429</code> with a <code>Retry-After</code> header.
          </p>
        </div>

        <div id="tenant-isolation" className="scroll-mt-20">
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-signal-amber" />
            <h2 className="text-lg font-semibold text-graphite-950 dark:text-graphite-50">Tenant isolation</h2>
          </div>
          <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Every query in every module filters by the authenticated organization&apos;s ID -- there is no
            cross-organization read path in the API. Roles (<code>owner</code>, <code>admin</code>, <code>member</code>,{" "}
            <code>viewer</code>) then gate what a member of your own organization can do once inside that boundary.
          </p>
        </div>

        <div id="headers" className="scroll-mt-20">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-signal-amber" />
            <h2 className="text-lg font-semibold text-graphite-950 dark:text-graphite-50">Response headers</h2>
          </div>
          <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-graphite-600 dark:text-graphite-400">
            Every API response carries <code>X-Content-Type-Options: nosniff</code>, <code>X-Frame-Options: DENY</code>,{" "}
            <code>Referrer-Policy: strict-origin-when-cross-origin</code>, a restrictive{" "}
            <code>Permissions-Policy</code>, and <code>X-Permitted-Cross-Domain-Policies: none</code>. In production,{" "}
            <code>Strict-Transport-Security</code> is added as well.
          </p>
        </div>
      </Section>
    </>
  );
}
