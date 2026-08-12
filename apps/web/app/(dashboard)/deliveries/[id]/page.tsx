"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { DeliveryJobOut } from "@/lib/types";
import { Card, CardHeader, CardBody, Badge } from "@/components/ui/card";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";
import { Skeleton } from "@/components/ui/skeleton";

export default function DeliveryDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<DeliveryJobOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<DeliveryJobOut>(`/v1/deliveries/${params.id}`)
      .then(setJob)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load delivery"));
  }, [params.id]);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <StatusDot color="red" size="md" />
        <p className="text-xs text-graphite-600 dark:text-graphite-400">{error}</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <button
        onClick={() => router.push("/deliveries")}
        className="flex w-fit items-center gap-1 text-xs text-graphite-600 hover:text-graphite-950 dark:text-graphite-400 dark:hover:text-graphite-50"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to deliveries
      </button>

      <div className="flex items-center gap-2">
        <h1 className="font-mono text-sm font-semibold text-graphite-950 dark:text-graphite-50">{job.event_type}</h1>
        <StatusDot color={statusToSignalColor(job.status)} label={job.status} />
      </div>

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Event payload</h2>
        </CardHeader>
        <CardBody>
          <pre className="overflow-x-auto rounded bg-graphite-50 p-3 font-mono text-xs text-graphite-800 dark:bg-graphite-800 dark:text-graphite-200">
            {JSON.stringify(job.payload, null, 2)}
          </pre>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Attempt history ({job.attempts.length})</h2>
        </CardHeader>
        <CardBody className="flex flex-col gap-3 p-0">
          {job.attempts.length === 0 ? (
            <div className="p-6 text-center text-xs text-graphite-500">No attempts recorded yet.</div>
          ) : (
            job.attempts.map((a) => (
              <div key={a.id} className="border-b border-graphite-100 p-4 last:border-0 dark:border-graphite-800">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="tabular text-xs font-medium text-graphite-950 dark:text-graphite-50">
                      Attempt {a.attempt_number}
                    </span>
                    {a.http_status && (
                      <Badge tone={a.http_status < 300 ? "green" : a.http_status < 500 ? "amber" : "red"}>
                        HTTP {a.http_status}
                      </Badge>
                    )}
                    {a.error_category !== "none" && <Badge tone="red">{a.error_category}</Badge>}
                  </div>
                  <span className="tabular text-xs text-graphite-500">{a.duration_ms}ms</span>
                </div>
                <div className="mt-1 flex gap-4 text-xs text-graphite-500">
                  <span>{new Date(a.started_at).toLocaleString()}</span>
                  <span className="font-mono">{a.worker_id}</span>
                  {a.destination_ip && <span className="font-mono">{a.destination_ip}</span>}
                </div>
                {a.error_message && <p className="mt-1.5 text-xs text-signal-red">{a.error_message}</p>}
                {a.response_body_truncated && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-graphite-600 hover:text-graphite-950 dark:text-graphite-400 dark:hover:text-graphite-50">
                      Response body
                    </summary>
                    <pre className="mt-1.5 overflow-x-auto rounded bg-graphite-50 p-2.5 font-mono text-[11px] text-graphite-700 dark:bg-graphite-800 dark:text-graphite-300">
                      {a.response_body_truncated}
                    </pre>
                  </details>
                )}
                {Object.keys(a.response_headers).length > 0 && (
                  <details className="mt-1.5">
                    <summary className="cursor-pointer text-xs text-graphite-600 hover:text-graphite-950 dark:text-graphite-400 dark:hover:text-graphite-50">
                      Response headers
                    </summary>
                    <pre className="mt-1.5 overflow-x-auto rounded bg-graphite-50 p-2.5 font-mono text-[11px] text-graphite-700 dark:bg-graphite-800 dark:text-graphite-300">
                      {JSON.stringify(a.response_headers, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            ))
          )}
        </CardBody>
      </Card>
    </div>
  );
}
