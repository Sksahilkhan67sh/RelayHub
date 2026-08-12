"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { RelayHubMark } from "@/components/ui/logo";

function InvitationSuccessInner() {
  const searchParams = useSearchParams();
  const org = searchParams.get("org") || "your new organization";

  return (
    <div className="flex min-h-screen items-center justify-center bg-graphite-50 px-4 dark:bg-graphite-950">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2">
          <RelayHubMark />
          <span className="text-base font-semibold text-graphite-950 dark:text-graphite-50">RelayHub</span>
        </div>

        <Card>
          <CardBody className="flex flex-col gap-3">
            <h1 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">You&apos;re in!</h1>
            <p className="text-xs text-graphite-600 dark:text-graphite-400">
              You&apos;ve joined <span className="font-medium text-graphite-950 dark:text-graphite-50">{org}</span> on
              RelayHub. You&apos;re already signed in.
            </p>
            <Link href="/dashboard">
              <Button className="mt-1 w-full">Go to dashboard</Button>
            </Link>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

export default function InvitationSuccessPage() {
  return (
    <Suspense fallback={null}>
      <InvitationSuccessInner />
    </Suspense>
  );
}
