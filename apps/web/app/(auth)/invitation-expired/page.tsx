"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Card, CardBody } from "@/components/ui/card";
import { RelayHubMark } from "@/components/ui/logo";

const COPY: Record<string, { title: string; body: (org: string) => string }> = {
  expired: {
    title: "Invitation expired",
    body: (org) => `This invitation to join ${org} has expired. Ask an admin at ${org} to send you a new one.`,
  },
  revoked: {
    title: "Invitation revoked",
    body: (org) => `This invitation to join ${org} was revoked by an admin and can no longer be used.`,
  },
  accepted: {
    title: "Invitation already used",
    body: (org) => `This invitation to join ${org} has already been accepted. If that was you, just sign in.`,
  },
};

function InvitationExpiredInner() {
  const searchParams = useSearchParams();
  const reason = searchParams.get("reason") || "expired";
  const org = searchParams.get("org") || "the organization";
  const copy = COPY[reason] ?? COPY.expired!;

  return (
    <div className="flex min-h-screen items-center justify-center bg-graphite-50 px-4 dark:bg-graphite-950">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2">
          <RelayHubMark />
          <span className="text-base font-semibold text-graphite-950 dark:text-graphite-50">RelayHub</span>
        </div>

        <Card>
          <CardBody className="flex flex-col gap-2">
            <h1 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">{copy.title}</h1>
            <p className="text-xs text-graphite-600 dark:text-graphite-400">{copy.body(org)}</p>
            <Link href="/login" className="mt-2 text-xs font-medium text-signal-amber hover:underline">
              Go to sign in
            </Link>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

export default function InvitationExpiredPage() {
  return (
    <Suspense fallback={null}>
      <InvitationExpiredInner />
    </Suspense>
  );
}
