import type { Metadata } from "next";
import { LegalLayout, LegalSection } from "@/components/marketing/legal-layout";

export const metadata: Metadata = {
  title: "Terms of Service — RelayHub",
  description: "The terms governing use of the RelayHub platform.",
  alternates: { canonical: "/terms" },
  openGraph: { title: "Terms of Service — RelayHub", description: "The terms governing use of the RelayHub platform.", url: "/terms" },
};

export default function TermsPage() {
  return (
    <LegalLayout title="Terms of Service" updated="August 1, 2026">
      <p>
        These terms govern your use of RelayHub, Inc.&apos;s (&quot;RelayHub&quot;) webhook and event delivery platform.
        By creating an account, you agree to these terms.
      </p>

      <LegalSection title="Accounts and organizations">
        <p>
          You&apos;re responsible for the accuracy of the information you provide and for maintaining the security of
          your account credentials and API keys. Actions taken under your organization&apos;s account -- by you or a
          teammate you&apos;ve invited -- are your organization&apos;s responsibility.
        </p>
      </LegalSection>

      <LegalSection title="Acceptable use">
        <p>You agree not to use RelayHub to:</p>
        <ul className="mt-2 flex flex-col gap-1.5 pl-4">
          <li className="list-disc">Deliver payloads that are unlawful, or that infringe on someone else&apos;s rights.</li>
          <li className="list-disc">Attempt to bypass rate limits, plan quotas, or access controls.</li>
          <li className="list-disc">Use the platform to deliver malware, or to conduct denial-of-service activity against a third party.</li>
          <li className="list-disc">Resell access to the platform without a separate written agreement with us.</li>
        </ul>
        <p className="mt-2">
          Accounts found in violation may be suspended; the admin panel&apos;s abuse-report queue exists specifically to
          triage and act on reports like this.
        </p>
      </LegalSection>

      <LegalSection title="Plans, billing, and limits">
        <p>
          Paid plans are billed on a recurring basis as described on the <a href="/pricing" className="text-signal-amber hover:underline">Pricing</a> page.
          If your organization exceeds its plan&apos;s delivery limit, new deliveries pause until you upgrade or the next
          billing cycle begins -- we do not bill for overages without your explicit upgrade. You may cancel a paid plan
          at any time from your billing settings; cancellation takes effect at the end of the current billing period.
        </p>
      </LegalSection>

      <LegalSection title="Data ownership">
        <p>
          You retain ownership of the event payloads and endpoint configurations you send through RelayHub. We process
          that data solely to operate the platform on your behalf, as described in our{" "}
          <a href="/privacy" className="text-signal-amber hover:underline">Privacy Policy</a>.
        </p>
      </LegalSection>

      <LegalSection title="Availability">
        <p>
          We work to keep RelayHub available and reliable, but we don&apos;t guarantee uninterrupted service. Current
          system status is published at <a href="/status" className="text-signal-amber hover:underline">relayhub.dev/status</a>.
          Enterprise plans may include a separate written SLA.
        </p>
      </LegalSection>

      <LegalSection title="Termination">
        <p>
          You may close your account at any time. We may suspend or terminate accounts that violate these terms,
          with notice where practical. On termination, your data is retained per our{" "}
          <a href="/privacy" className="text-signal-amber hover:underline">Privacy Policy</a> and then deleted.
        </p>
      </LegalSection>

      <LegalSection title="Limitation of liability">
        <p>
          RelayHub is provided on an &quot;as is&quot; basis. To the extent permitted by law, RelayHub is not liable for
          indirect, incidental, or consequential damages arising from use of the platform, including losses resulting
          from a missed or delayed webhook delivery beyond the retry policy you&apos;ve configured.
        </p>
      </LegalSection>

      <LegalSection title="Changes to these terms">
        <p>We&apos;ll update the date at the top of this page when these terms change, and notify account owners by email of material changes.</p>
      </LegalSection>

      <LegalSection title="Contact">
        <p>
          Questions about these terms: <a href="mailto:legal@relayhub.dev" className="text-signal-amber hover:underline">legal@relayhub.dev</a>, or use the{" "}
          <a href="/contact" className="text-signal-amber hover:underline">contact form</a>.
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
