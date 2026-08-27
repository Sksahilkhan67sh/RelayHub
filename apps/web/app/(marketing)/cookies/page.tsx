import type { Metadata } from "next";
import { LegalLayout, LegalSection } from "@/components/marketing/legal-layout";

export const metadata: Metadata = {
  title: "Cookie Policy — RelayHub",
  description: "What RelayHub stores in your browser, and why.",
  alternates: { canonical: "/cookies" },
  openGraph: { title: "Cookie Policy — RelayHub", description: "What RelayHub stores in your browser, and why.", url: "/cookies" },
};

export default function CookiesPage() {
  return (
    <LegalLayout title="Cookie Policy" updated="August 1, 2026">
      <p>
        RelayHub doesn&apos;t use tracking or advertising cookies -- there&apos;s no analytics pixel or ad network script
        anywhere on this site or in the dashboard. What we do use is your browser&apos;s local storage, for a short,
        specific list of things:
      </p>

      <LegalSection title="What we store, and why">
        <ul className="mt-1 flex flex-col gap-1.5 pl-4">
          <li className="list-disc"><span className="font-medium text-graphite-950 dark:text-graphite-50">Session tokens</span> -- your access and refresh tokens, so you stay signed in between visits.</li>
          <li className="list-disc"><span className="font-medium text-graphite-950 dark:text-graphite-50">Theme preference</span> -- whether you&apos;ve chosen light, dark, or system, so the dashboard renders correctly on your next visit without a flash of the wrong theme.</li>
          <li className="list-disc"><span className="font-medium text-graphite-950 dark:text-graphite-50">Recent command palette actions</span> -- the last few things you searched for or opened via Cmd/Ctrl+K, purely so the palette can show your recents.</li>
        </ul>
      </LegalSection>

      <LegalSection title="Why local storage instead of cookies">
        <p>
          Local storage keeps this data on your device and out of every outgoing HTTP request by default, unlike a
          cookie, which browsers attach automatically. We know this has a tradeoff -- it&apos;s more exposed to
          cross-site scripting than an httpOnly cookie would be -- and moving session tokens to a server-managed cookie
          is on our engineering roadmap. Until then, we mitigate the risk by keeping our client-side code
          dependency-light and reviewed.
        </p>
      </LegalSection>

      <LegalSection title="Third parties">
        <p>
          We do not embed third-party trackers, advertising networks, or session-replay tools on RelayHub&apos;s
          marketing site or dashboard. If that changes, we&apos;ll update this page and the date above.
        </p>
      </LegalSection>

      <LegalSection title="Clearing this data">
        <p>
          Signing out clears your session tokens. Clearing your browser&apos;s local storage for this site removes
          everything listed above -- you&apos;ll simply be signed out and your theme preference will reset to
          &quot;system&quot; on your next visit.
        </p>
      </LegalSection>

      <LegalSection title="Contact">
        <p>
          Questions: <a href="mailto:privacy@relayhub.dev" className="text-signal-amber hover:underline">privacy@relayhub.dev</a>, or use the{" "}
          <a href="/contact" className="text-signal-amber hover:underline">contact form</a>.
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
