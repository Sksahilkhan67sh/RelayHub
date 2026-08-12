"use client";

import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardBody } from "@/components/ui/card";
import { RelayHubMark } from "@/components/ui/logo";

function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-graphite-50 px-4 dark:bg-graphite-950">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2">
          <RelayHubMark />
          <span className="text-base font-semibold text-graphite-950 dark:text-graphite-50">RelayHub</span>
        </div>
        {children}
      </div>
    </div>
  );
}

function ResetPasswordInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") || "";

  const [newPassword, setNewPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/v1/auth/reset-password", { token, new_password: newPassword });
      setDone(true);
      setTimeout(() => router.push("/login"), 2000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <AuthShell>
        <Card>
          <CardBody className="flex flex-col gap-2">
            <h1 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">Invalid reset link</h1>
            <p className="text-xs text-graphite-600 dark:text-graphite-400">
              This link is missing its token. Request a new one from the sign-in page.
            </p>
            <Link href="/forgot-password" className="mt-2 text-xs font-medium text-signal-amber hover:underline">
              Request new link
            </Link>
          </CardBody>
        </Card>
      </AuthShell>
    );
  }

  if (done) {
    return (
      <AuthShell>
        <Card>
          <CardBody className="flex flex-col gap-2">
            <h1 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">Password updated</h1>
            <p className="text-xs text-graphite-600 dark:text-graphite-400">
              You&apos;ve been signed out everywhere for security. Redirecting you to sign in&hellip;
            </p>
          </CardBody>
        </Card>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <Card>
        <CardBody className="flex flex-col gap-4">
          <div>
            <h1 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">Choose a new password</h1>
            <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
              This link can only be used once and expires 30 minutes after it was sent.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <Input
              label="New password"
              type="password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              hint="At least 8 characters, one uppercase letter, one digit"
            />
            {error && <p className="text-xs text-signal-red">{error}</p>}
            <Button type="submit" loading={submitting} className="mt-1 w-full">
              Update password
            </Button>
          </form>
        </CardBody>
      </Card>
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordInner />
    </Suspense>
  );
}
