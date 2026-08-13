import Link from "next/link";
import { RelayHubMark } from "@/components/ui/logo";

const COLUMNS: { title: string; links: { href: string; label: string }[] }[] = [
  {
    title: "Product",
    links: [
      { href: "/features", label: "Features" },
      { href: "/pricing", label: "Pricing" },
      { href: "/changelog", label: "Changelog" },
      { href: "/status", label: "Status" },
    ],
  },
  {
    title: "Developers",
    links: [
      { href: "/docs", label: "Documentation" },
      { href: "/docs#api-keys", label: "API keys" },
      { href: "/docs#webhooks", label: "Webhooks" },
      { href: "/status", label: "System status" },
    ],
  },
  {
    title: "Company",
    links: [
      { href: "/about", label: "About" },
      { href: "/founder", label: "Founder" },
      { href: "/careers", label: "Careers" },
      { href: "/blog", label: "Blog" },
      { href: "/contact", label: "Contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { href: "/privacy", label: "Privacy policy" },
      { href: "/terms", label: "Terms of service" },
      { href: "/cookies", label: "Cookie policy" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="border-t border-graphite-800 bg-graphite-950 text-graphite-400">
      <div className="mx-auto max-w-6xl px-5 py-14">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-3 lg:grid-cols-6">
          <div className="col-span-2 lg:col-span-2">
            <Link href="/" className="flex items-center gap-2">
              <RelayHubMark size={22} />
              <span className="text-sm font-semibold text-white">RelayHub</span>
            </Link>
            <p className="mt-3 max-w-xs text-xs leading-relaxed text-graphite-500">
              Webhook and event delivery infrastructure for teams who need every event to land, every time.
            </p>
          </div>

          {COLUMNS.map((col) => (
            <div key={col.title}>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-graphite-300">{col.title}</h3>
              <ul className="mt-3 flex flex-col gap-2.5">
                {col.links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-xs text-graphite-500 transition-colors hover:text-graphite-200">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col-reverse items-center justify-between gap-4 border-t border-graphite-800 pt-6 sm:flex-row">
          <p className="text-xs text-graphite-600">&copy; {new Date().getFullYear()} RelayHub, Inc. All rights reserved.</p>
          <Link href="/status" className="text-xs text-graphite-500 hover:text-graphite-200">
            System status →
          </Link>
        </div>
      </div>
    </footer>
  );
}
