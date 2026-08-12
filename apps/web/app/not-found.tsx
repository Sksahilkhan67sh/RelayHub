import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { RelayHubMark } from "@/components/ui/logo";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-graphite-950 px-5 text-center">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-24 top-1/4 h-96 w-96 rounded-full bg-signal-amber/10 blur-3xl"
        style={{ animation: "relay-drift 14s ease-in-out infinite" }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-24 bottom-1/4 h-96 w-96 rounded-full bg-signal-green/10 blur-3xl"
        style={{ animation: "relay-drift 18s ease-in-out infinite reverse" }}
      />

      <Link href="/" className="relative z-10 mb-10 flex items-center gap-2">
        <RelayHubMark size={26} />
        <span className="text-base font-semibold text-white">RelayHub</span>
      </Link>

      <div
        className="relative z-10 flex h-16 w-16 items-center justify-center rounded-full border border-graphite-700 bg-graphite-900"
        style={{ animation: "relay-hub-glow 2.6s infinite ease-in-out" }}
      >
        <span className="font-mono text-lg text-signal-red">404</span>
      </div>

      <h1 className="relative z-10 mt-8 text-3xl font-semibold tracking-tight text-white sm:text-4xl">This endpoint doesn&apos;t exist</h1>
      <p className="relative z-10 mt-3 max-w-sm text-sm text-graphite-400">
        We checked the delivery log -- there&apos;s no route subscribed at this URL. It may have moved, or the link might
        just be wrong.
      </p>

      <Link href="/" className="relative z-10 mt-8">
        <Button size="md">
          <ArrowLeft className="h-3.5 w-3.5" />
          Return home
        </Button>
      </Link>
    </div>
  );
}
