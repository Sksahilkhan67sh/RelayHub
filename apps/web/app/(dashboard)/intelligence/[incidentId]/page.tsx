"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Sparkles, FileCheck2 } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import type { IncidentDetailOut, IncidentTimelineOut } from "@/lib/types";
import { Card, CardHeader, CardBody, Badge } from "@/components/ui/card";
import { StatusDot, statusToSignalColor } from "@/components/ui/status-dot";
import { Skeleton } from "@/components/ui/skeleton";

export default function IncidentDetailPage() {
  const params = useParams<{ incidentId: string }>();
  const [incident, setIncident] = useState<IncidentDetailOut | null>(null);
  const [timeline, setTimeline] = useState<IncidentTimelineOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params.incidentId) return;
    Promise.all([
      api.get<IncidentDetailOut>(`/v1/insights/intelligence/incidents/${params.incidentId}`),
      api.get<IncidentTimelineOut>(`/v1/insights/intelligence/incidents/${params.incidentId}/timeline`),
    ])
      .then(([i, t]) => {
        setIncident(i);
        setTimeline(t);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load incident"));
  }, [params.incidentId]);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <StatusDot color="red" size="md" />
        <p className="text-xs text-graphite-600 dark:text-graphite-400">{error}</p>
      </div>
    );
  }

  if (!incident) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  const deterministicRca = incident.rca_entries.find((r) => r.source === "deterministic");
  const aiRca = incident.rca_entries.find((r) => r.source === "ai");
  const recommendations = (aiRca ?? deterministicRca)?.recommendations ?? [];

  return (
    <div className="flex flex-col gap-5">
      <Link href="/intelligence" className="flex w-fit items-center gap-1 text-xs text-graphite-500 hover:text-graphite-800 dark:hover:text-graphite-200">
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to Intelligence
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <StatusDot color={statusToSignalColor(incident.status)} size="md" />
            <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">{incident.title}</h1>
          </div>
          <p className="mt-1 text-xs text-graphite-600 dark:text-graphite-400">{incident.summary}</p>
        </div>
        <Badge tone={incident.severity === "critical" ? "red" : incident.severity === "warning" ? "amber" : "neutral"}>
          {incident.severity}
        </Badge>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 text-xs">
        <MetaField label="Status" value={incident.status} />
        <MetaField label="Failure category" value={incident.failure_category.replace(/_/g, " ")} />
        <MetaField label="Opened" value={new Date(incident.opened_at).toLocaleString()} />
        <MetaField label="Last signal" value={new Date(incident.last_signal_at).toLocaleString()} />
      </div>

      {/* Root Cause Analysis -- FACT (deterministic, evidence-derived) vs AI INFERENCE
          (provider narrative) are rendered as visually distinct sections, never
          merged into one block, per the brief's explicit requirement that these
          never be presented as equivalent. */}
      <section className="flex flex-col gap-3">
        <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Root cause analysis</h2>

        {deterministicRca && (
          <Card className="border-l-2 border-l-graphite-400">
            <CardHeader className="flex items-center gap-2">
              <FileCheck2 className="h-3.5 w-3.5 text-graphite-500" />
              <span className="text-xs font-semibold uppercase tracking-wide text-graphite-500">Fact — deterministic</span>
              <ConfidenceBadge level={deterministicRca.confidence_level} score={deterministicRca.confidence_score} />
            </CardHeader>
            <CardBody className="flex flex-col gap-3">
              <p className="text-xs text-graphite-800 dark:text-graphite-200">{deterministicRca.likely_cause}</p>
              <EvidenceList evidence={deterministicRca.evidence} />
            </CardBody>
          </Card>
        )}

        {aiRca ? (
          <Card className="border-l-2 border-l-signal-amber">
            <CardHeader className="flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 text-signal-amber" />
              <span className="text-xs font-semibold uppercase tracking-wide text-signal-amber">AI inference</span>
              <ConfidenceBadge level={aiRca.confidence_level} score={aiRca.confidence_score} />
              {aiRca.ai_provider && (
                <span className="ml-auto text-[10px] text-graphite-400">
                  {aiRca.ai_provider} · {aiRca.ai_model}
                </span>
              )}
            </CardHeader>
            <CardBody className="flex flex-col gap-3">
              <p className="text-xs text-graphite-800 dark:text-graphite-200">{aiRca.likely_cause}</p>
              <p className="text-[10px] text-graphite-400">
                AI-generated narrative, produced from the same evidence shown above. Treat as an inference to verify, not a
                fact.
              </p>
              <EvidenceList evidence={aiRca.evidence} />
            </CardBody>
          </Card>
        ) : (
          <p className="text-[10px] text-graphite-400">
            No AI inference available for this incident (AI enrichment disabled, not yet run, or the provider was
            unavailable — the deterministic analysis above is unaffected either way).
          </p>
        )}
      </section>

      {recommendations.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Recommendations</h2>
          <Card>
            <CardBody>
              <ul className="flex flex-col gap-2">
                {recommendations.map((rec, i) => (
                  <li key={i} className="flex gap-2 text-xs text-graphite-800 dark:text-graphite-200">
                    <span className="text-graphite-400">→</span>
                    {rec}
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        </section>
      )}

      <section className="flex flex-col gap-2">
        <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Anomalies ({incident.anomalies.length})</h2>
        <Card>
          <CardBody className="p-0">
            {incident.anomalies.length === 0 ? (
              <div className="p-4 text-center text-xs text-graphite-500">No anomalies attached to this incident.</div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                    <th className="px-4 py-2 font-medium">Metric</th>
                    <th className="px-4 py-2 font-medium">Direction</th>
                    <th className="px-4 py-2 font-medium">Observed at</th>
                  </tr>
                </thead>
                <tbody>
                  {incident.anomalies.map((a) => (
                    <tr key={a.id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-900">
                      <td className="px-4 py-2.5 font-medium text-graphite-900 dark:text-graphite-100">
                        {a.metric.replace(/_/g, " ")}
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge tone={a.direction === "spike" || a.direction === "regression" ? "red" : "green"}>
                          {a.direction}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5 text-graphite-500">{new Date(a.observed_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardBody>
        </Card>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Timeline</h2>
        <Card>
          <CardBody>
            {timeline === null ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              <ol className="flex flex-col gap-3">
                {timeline.events.map((event, i) => (
                  <li key={i} className="flex gap-3 text-xs">
                    <div className="flex flex-col items-center">
                      <span className="h-1.5 w-1.5 rounded-full bg-graphite-400" />
                      {i < timeline.events.length - 1 && <span className="mt-1 w-px flex-1 bg-graphite-100 dark:bg-graphite-800" />}
                    </div>
                    <div className="pb-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium capitalize text-graphite-900 dark:text-graphite-100">
                          {event.type.replace(/_/g, " ")}
                        </span>
                        <span className="text-[10px] text-graphite-400">{new Date(event.at).toLocaleString()}</span>
                      </div>
                      <p className="text-graphite-600 dark:text-graphite-400">{event.detail}</p>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </CardBody>
        </Card>
      </section>
    </div>
  );
}

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wide text-graphite-400">{label}</span>
      <span className="capitalize text-graphite-800 dark:text-graphite-200">{value}</span>
    </div>
  );
}

function ConfidenceBadge({ level, score }: { level: string; score: number }) {
  const tone = level === "confirmed" || level === "highly_likely" ? "green" : level === "likely" ? "amber" : "neutral";
  return (
    <Badge tone={tone}>
      {level.replace(/_/g, " ")} ({(score * 100).toFixed(0)}%)
    </Badge>
  );
}

function EvidenceList({ evidence }: { evidence: { label: string; value: string | number }[] }) {
  if (evidence.length === 0) return null;
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 border-t border-graphite-100 pt-3 dark:border-graphite-800">
      {evidence.map((e, i) => (
        <div key={i} className="flex justify-between gap-2 text-[11px]">
          <dt className="text-graphite-500">{e.label}</dt>
          <dd className="tabular text-graphite-800 dark:text-graphite-200">{e.value}</dd>
        </div>
      ))}
    </dl>
  );
}
