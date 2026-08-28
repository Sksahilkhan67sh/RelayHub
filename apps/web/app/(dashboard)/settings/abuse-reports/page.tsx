"use client";

import { useEffect, useState, type FormEvent } from "react";
import { AlertTriangle } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { AbuseReportOut } from "@/lib/types";
import { Card, CardHeader, CardBody, Badge } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";

function statusTone(status: string) {
  if (status === "open") return "red" as const;
  if (status === "investigating") return "amber" as const;
  return "neutral" as const;
}

export default function OrgAbuseReportsPage() {
  const { me } = useAuth();
  const canViewHistory = me?.role === "owner" || me?.role === "admin";

  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const [reports, setReports] = useState<AbuseReportOut[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  async function loadReports() {
    if (!canViewHistory) return;
    try {
      const data = await api.get<AbuseReportOut[]>("/v1/org/abuse-reports");
      setReports(data);
    } catch (err) {
      setListError(err instanceof ApiError ? err.message : "Failed to load abuse reports");
    }
  }

  useEffect(() => {
    loadReports();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canViewHistory]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setSubmitted(false);
    setSubmitting(true);
    try {
      await api.post("/v1/org/abuse-reports", { reason });
      setReason("");
      setSubmitted(true);
      await loadReports();
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Failed to submit report");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Abuse Reports</h1>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
          Flag something on your organization&apos;s account for our platform team to review.
        </p>
      </div>

      <Card className="max-w-lg">
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Report an issue</h2>
        </CardHeader>
        <CardBody>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <Textarea
              label="What's going on?"
              required
              minLength={1}
              maxLength={2000}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Describe the activity or issue you'd like us to look into..."
            />
            {submitError && <p className="text-xs text-signal-red">{submitError}</p>}
            {submitted && <p className="text-xs text-signal-green">Report submitted. Our team will review it shortly.</p>}
            <Button type="submit" size="sm" loading={submitting} className="self-start">
              Submit report
            </Button>
          </form>
        </CardBody>
      </Card>

      {canViewHistory && (
        <>
          <div className="mt-2">
            <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Report history</h2>
            <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
              All reports on file for your organization, including ones filed by platform admins.
            </p>
          </div>

          <Card>
            {reports === null ? (
              <TableSkeleton rows={3} />
            ) : listError ? (
              <div className="p-6 text-center text-xs text-signal-red">{listError}</div>
            ) : reports.length === 0 ? (
              <EmptyState
                icon={AlertTriangle}
                title="No reports"
                description="Your organization has no abuse reports on file."
              />
            ) : (
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                    <th className="px-4 py-2 font-medium">Reason</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Filed</th>
                    <th className="px-4 py-2 font-medium">Resolution</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map((r) => (
                    <tr key={r.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                      <td className="max-w-[320px] px-4 py-2.5 text-graphite-950 dark:text-graphite-50">{r.reason}</td>
                      <td className="px-4 py-2.5">
                        <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                      </td>
                      <td className="tabular px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                        {new Date(r.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-2.5 text-graphite-600 dark:text-graphite-400">
                        {r.resolution_notes ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
