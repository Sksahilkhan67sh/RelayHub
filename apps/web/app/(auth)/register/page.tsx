"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth, getAuthErrorMessage } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardBody } from "@/components/ui/card";
import { RelayHubMark } from "@/components/ui/logo";

export default function RegisterPage() {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register({ email, password, full_name: fullName, organization_name: orgName });
    } catch (err) {
      setError(getAuthErrorMessage(err));
    } finally {
      setLoading(false);
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
              <h1 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">Create your account</h1>
              <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
                Start delivering webhooks reliably in minutes.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <Input label="Full name" required value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" />
              <Input
                label="Organization name"
                required
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="Acme Inc."
              />
              <Input
                label="Email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
              />
              <Input
                label="Password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                hint="At least 8 characters, one uppercase letter, one digit"
              />
              {error && <p className="text-xs text-signal-red">{error}</p>}
              <Button type="submit" loading={loading} className="mt-1 w-full">
                Create account
              </Button>
            </form>
          </CardBody>
        </Card>

        <p className="mt-4 text-center text-xs text-graphite-600 dark:text-graphite-400">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-signal-amber hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
