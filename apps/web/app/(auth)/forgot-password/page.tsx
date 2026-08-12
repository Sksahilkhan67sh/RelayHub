"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardBody } from "@/components/ui/card";
import { RelayHubMark } from "@/components/ui/logo";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/v1/auth/forgot-password", { email });
      // The backend always returns the same generic response whether or not the
      // email belongs to an account -- the UI mirrors that and never reveals which.
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-graphite-50 px-4 dark:bg-graphite-950">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2">
          <RelayHubMark />
          <span className="text-base font-semibold text-graphite-950 dark:text-graphite-50">RelayHub</span>
        </div>

        <Card>
          <CardBody className="flex flex-col gap-4">
            <div>
              <h1 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">Reset your password</h1>
              <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
                Enter your account email and we&apos;ll send you a reset link.
              </p>
            </div>

            {sent ? (
              <p className="text-xs text-graphite-600 dark:text-graphite-400">
                If an account exists for <span className="font-medium text-graphite-950 dark:text-graphite-50">{email}</span>,
                a password reset link is on its way. It expires in 30 minutes.
              </p>
            ) : (
              <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                <Input
                  label="Email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                />
                {error && <p className="text-xs text-signal-red">{error}</p>}
                <Button type="submit" loading={submitting} className="mt-1 w-full">
                  Send reset link
                </Button>
              </form>
            )}

            <Link href="/login" className="text-xs font-medium text-signal-amber hover:underline">
              Back to sign in
            </Link>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
