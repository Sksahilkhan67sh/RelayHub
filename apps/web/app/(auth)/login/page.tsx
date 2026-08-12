"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth, getAuthErrorMessage } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardBody } from "@/components/ui/card";
import { RelayHubMark } from "@/components/ui/logo";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
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
            <h1 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">Sign in</h1>

            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <Input
                label="Email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
              />
              <div>
                <Input
                  label="Password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
                <Link href="/forgot-password" className="mt-1.5 inline-block text-xs text-graphite-600 hover:text-signal-amber dark:text-graphite-400">
                  Forgot password?
                </Link>
              </div>
              {error && <p className="text-xs text-signal-red">{error}</p>}
              <Button type="submit" loading={loading} className="mt-1 w-full">
                Sign in
              </Button>
            </form>
          </CardBody>
        </Card>

        <p className="mt-4 text-center text-xs text-graphite-600 dark:text-graphite-400">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="font-medium text-signal-amber hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
