"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { api, setTokens, ApiError } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardBody, Badge } from "@/components/ui/card";
import { RelayHubMark } from "@/components/ui/logo";

interface InvitationPublicOut {
  organization_name: string;
  email: string;
  role: string;
  status: "pending" | "accepted" | "revoked" | "expired";
  expires_at: string;
}

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

function AcceptInvitationInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") || "";

  const [invitation, setInvitation] = useState<InvitationPublicOut | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingInvite, setLoadingInvite] = useState(true);

  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [needsAccountFields, setNeedsAccountFields] = useState(false);

  useEffect(() => {
    if (!token) {
      setLoadError("This invitation link is missing its token.");
      setLoadingInvite(false);
      return;
    }
    api
      .get<InvitationPublicOut>(`/v1/invitations/${encodeURIComponent(token)}`)
      .then((data) => {
        setInvitation(data);
        if (data.status !== "pending") {
          router.replace(`/invitation-expired?reason=${data.status}&org=${encodeURIComponent(data.organization_name)}`);
        }
      })
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "This invitation could not be found."))
      .finally(() => setLoadingInvite(false));
  }, [token, router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      const data = await api.post<{ access_token: string; refresh_token: string }>("/v1/invitations/accept", {
        token,
        full_name: needsAccountFields ? fullName : undefined,
        password: needsAccountFields ? password : undefined,
      });
      setTokens(data.access_token, data.refresh_token);
      router.push(`/invitation-success?org=${encodeURIComponent(invitation?.organization_name || "")}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400 && !needsAccountFields) {
        // No account exists yet for this email -- reveal the name/password fields
        // the backend needs to create one, rather than treating this as a failure.
        setNeedsAccountFields(true);
      } else {
        setSubmitError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loadingInvite) {
    return (
      <AuthShell>
        <Card>
          <CardBody>
            <p className="text-sm text-graphite-600 dark:text-graphite-400">Loading invitation…</p>
          </CardBody>
        </Card>
      </AuthShell>
    );
  }

  if (loadError || !invitation) {
    return (
      <AuthShell>
        <Card>
          <CardBody className="flex flex-col gap-2">
            <h1 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">Invitation not found</h1>
            <p className="text-xs text-graphite-600 dark:text-graphite-400">
              {loadError || "This invitation link is invalid."}
            </p>
            <Link href="/login" className="mt-2 text-xs font-medium text-signal-amber hover:underline">
              Go to sign in
            </Link>
          </CardBody>
        </Card>
      </AuthShell>
    );
  }

  if (invitation.status !== "pending") {
    // Already redirected to /invitation-expired above; render nothing in the meantime.
    return null;
  }

  return (
    <AuthShell>
      <Card>
        <CardBody className="flex flex-col gap-4">
          <div>
            <h1 className="text-base font-semibold text-graphite-950 dark:text-graphite-50">
              Join {invitation.organization_name}
            </h1>
            <p className="mt-0.5 flex items-center gap-1.5 text-xs text-graphite-600 dark:text-graphite-400">
              You&apos;ve been invited as <Badge tone="amber">{invitation.role}</Badge>
              <span>({invitation.email})</span>
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            {needsAccountFields && (
              <>
                <p className="text-xs text-graphite-600 dark:text-graphite-400">
                  No RelayHub account exists for this email yet -- set a name and password to create one.
                </p>
                <Input
                  label="Full name"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  autoComplete="name"
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
              </>
            )}
            {submitError && <p className="text-xs text-signal-red">{submitError}</p>}
            <Button type="submit" loading={submitting} className="mt-1 w-full">
              {needsAccountFields ? "Create account & join" : "Accept invitation"}
            </Button>
          </form>

          {!needsAccountFields && (
            <p className="text-xs text-graphite-600 dark:text-graphite-400">
              Already have a RelayHub account with a different session?{" "}
              <Link href="/login" className="font-medium text-signal-amber hover:underline">
                Sign in
              </Link>{" "}
              first, then come back to this link.
            </p>
          )}
        </CardBody>
      </Card>
    </AuthShell>
  );
}

export default function AcceptInvitationPage() {
  return (
    <Suspense fallback={null}>
      <AcceptInvitationInner />
    </Suspense>
  );
}
