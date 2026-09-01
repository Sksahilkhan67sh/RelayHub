"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { setTokens } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { Card, CardBody } from "@/components/ui/card";
import { RelayHubMark } from "@/components/ui/logo";

/**
 * Landing page for the GitHub OAuth redirect (backend: auth/github_oauth_routes.py).
 * Tokens arrive in the URL *fragment* (`#access_token=...&refresh_token=...`), not a
 * query string, specifically so they're never sent to any server (no Referer/access-log
 * leakage) -- only this page's own client-side JS ever reads them. `window.location.hash`
 * is only available client-side, hence reading it in an effect rather than via
 * useSearchParams (which only sees the query string, not the fragment).
 */
export default function GitHubCallbackPage() {
  const router = useRouter();
  const { refetchMe } = useAuth();
  const [error, setError] = useState(false);

  useEffect(() => {
    const hash = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : window.location.hash;
    const params = new URLSearchParams(hash);
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");

    if (!accessToken || !refreshToken) {
      setError(true);
      return;
    }

    setTokens(accessToken, refreshToken);
    // Strip the tokens out of the URL immediately so they don't linger in
    // browser history any longer than necessary.
    window.history.replaceState(null, "", window.location.pathname);

    refetchMe().then(() => router.replace("/dashboard"));
  }, [refetchMe, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-graphite-50 px-4 dark:bg-graphite-950">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2">
          <RelayHubMark />
          <span className="text-base font-semibold text-graphite-950 dark:text-graphite-50">RelayHub</span>
        </div>

        <Card>
          <CardBody className="flex flex-col gap-3">
            {error ? (
              <>
                <h1 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">
                  Sign-in didn&apos;t complete
                </h1>
                <p className="text-xs text-graphite-600 dark:text-graphite-400">
                  Something went wrong finishing GitHub sign-in.{" "}
                  <a href="/login" className="font-medium text-signal-amber hover:underline">
                    Back to sign in
                  </a>
                </p>
              </>
            ) : (
              <p className="text-xs text-graphite-600 dark:text-graphite-400">Signing you in&hellip;</p>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
