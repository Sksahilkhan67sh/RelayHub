"use client";

import { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { api, ApiError, getAccessToken } from "@/lib/api-client";
import type { AnalyticsSummary, TimeSeriesBucket, TopEndpoint, UsageSummary } from "@/lib/types";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { OnboardingChecklist } from "@/components/dashboard/onboarding-checklist";
import { DateRangeFilter, resolvePreset, type DateRange } from "@/components/dashboard/date-range-filter";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { StatusDot } from "@/components/ui/status-dot";
import { Button } from "@/components/ui/button";
import { Loader2, Download } from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Buckets by hour read fine over a single day, but blow up into an unreadable
// wall of points over a week+ window -- switch to daily buckets once the
// selected range spans more than ~2 days.
function granularityFor(range: DateRange): "hour" | "day" {
  if (!range.start || !range.end) return "day"; // "Overall" -- always daily buckets
  const spanMs = new Date(range.end).getTime() - new Date(range.start).getTime();
  return spanMs > 2 * 24 * 60 * 60 * 1000 ? "day" : "hour";
}

export default function DashboardPage() {
  const [range, setRange] = useState<DateRange>(() => resolvePreset("today"));
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [timeSeries, setTimeSeries] = useState<TimeSeriesBucket[]>([]);
  const [topEndpoints, setTopEndpoints] = useState<TopEndpoint[]>([]);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<"deliveries-over-time" | "top-endpoints" | null>(null);

  async function handleExport(report: "deliveries-over-time" | "top-endpoints") {
    setExporting(report);
    try {
      const dateParams =
        range.start && range.end
          ? `&start_date=${encodeURIComponent(range.start)}&end_date=${encodeURIComponent(range.end)}`
          : "";
      const token = getAccessToken();
      // /v1/insights is an alias of /v1/analytics -- see the note above and
      // backend/app/modules/analytics/routes.py's module docstring.
      const resp = await fetch(
        `${API_BASE_URL}/v1/insights/export?report=${report}&granularity=${granularityFor(range)}${dateParams}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      if (!resp.ok) {
        alert("Failed to export CSV");
        return;
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `relayhub_${report}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Failed to export CSV");
    } finally {
      setExporting(null);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        // "Overall" (and an unset custom range) has null start/end -- omit the
        // params entirely so the API's own all-time default applies, rather than
        // sending start_date=null/end_date=null as literal query values.
        const dateParams =
          range.start && range.end
            ? `start_date=${encodeURIComponent(range.start)}&end_date=${encodeURIComponent(range.end)}`
            : "";
        const sep = dateParams ? "&" : "";
        const granularity = granularityFor(range);

        const [summaryData, timeSeriesData, topEndpointsData, usageData] = await Promise.all([
          // /v1/insights is an alias of /v1/analytics used by this first-party
          // dashboard specifically to avoid ad-blocker filter lists that match
          // "analytics" in request URLs -- see
          // backend/app/modules/analytics/routes.py's module docstring.
          api.get<AnalyticsSummary>(`/v1/insights/summary${dateParams ? `?${dateParams}` : ""}`),
          api.get<TimeSeriesBucket[]>(`/v1/insights/deliveries-over-time?granularity=${granularity}${sep}${dateParams}`),
          api.get<TopEndpoint[]>(`/v1/insights/top-endpoints?limit=5${sep}${dateParams}`),
          api.get<UsageSummary>("/v1/billing/usage"),
        ]);
        if (cancelled) return;
        setSummary(summaryData);
        setTimeSeries(timeSeriesData);
        setTopEndpoints(topEndpointsData);
        setUsage(usageData);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Failed to load dashboard data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [range]);

  if (loading && !summary) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-graphite-400" />
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Dashboard</h1>
        <DateRangeFilter value={range.preset} onChange={setRange} />
      </div>

      <OnboardingChecklist />

      {loading && (
        <div className="flex items-center gap-1.5 text-xs text-graphite-500">
          <Loader2 className="h-3 w-3 animate-spin" /> Updating for {range.label}…
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard label={`Overall deliveries (${range.label})`} value={summary?.total_deliveries ?? 0} />
        <KpiCard label="Successful deliveries" value={summary?.success_count ?? 0} tone="green" />
        <KpiCard
          label="Success rate"
          value={summary?.success_rate != null ? `${(summary.success_rate * 100).toFixed(1)}%` : "—"}
          tone="green"
        />
        <KpiCard label="Failed deliveries" value={summary?.failed_count ?? 0} tone={summary?.failed_count ? "red" : undefined} />
        <KpiCard label="Retrying jobs" value={summary?.retrying_count ?? 0} tone={summary?.retrying_count ? "amber" : undefined} />
        <KpiCard label="Dead letter count" value={summary?.dead_letter_count ?? 0} tone={summary?.dead_letter_count ? "red" : undefined} />
        <KpiCard label="Active endpoints" value={usage?.endpoint_count ?? 0} />
        <KpiCard label="Events published" value={summary?.total_events ?? 0} />
        <KpiCard label="p95 latency" value={summary?.latency_p95_ms != null ? Math.round(summary.latency_p95_ms) : "—"} suffix="ms" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex items-center justify-between gap-3">
            <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">
              Deliveries {granularityFor(range) === "hour" ? "per hour" : "per day"} — {range.label}
            </h2>
            {timeSeries.length > 0 && (
              <Button
                size="sm"
                variant="secondary"
                loading={exporting === "deliveries-over-time"}
                onClick={() => handleExport("deliveries-over-time")}
              >
                <Download className="h-3.5 w-3.5" />
                Export CSV
              </Button>
            )}
          </CardHeader>
          <CardBody>
            {timeSeries.length === 0 ? (
              <EmptyChartState />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={timeSeries}>
                  <defs>
                    <linearGradient id="deliveryFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#C17F2B" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#C17F2B" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E7E9EC" vertical={false} />
                  <XAxis
                    dataKey="bucket"
                    tick={{ fontSize: 11, fill: "#8A9099" }}
                    tickFormatter={(v: string) => v.slice(5, 16)}
                    axisLine={{ stroke: "#E7E9EC" }}
                    tickLine={false}
                  />
                  <YAxis tick={{ fontSize: 11, fill: "#8A9099" }} axisLine={false} tickLine={false} width={30} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 6, border: "1px solid #E7E9EC" }}
                    labelFormatter={(v: string) => v}
                  />
                  <Area type="monotone" dataKey="total_count" stroke="#C17F2B" fill="url(#deliveryFill)" strokeWidth={1.5} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Plan usage</h2>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            <UsageBar
              label="Deliveries this period"
              current={usage?.delivery_count ?? 0}
              max={usage?.max_deliveries_per_month ?? null}
            />
            <UsageBar label="Endpoints" current={usage?.endpoint_count ?? 0} max={usage?.max_endpoints ?? null} />
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex items-center justify-between gap-3">
          <h2 className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Top endpoints — {range.label}</h2>
          {topEndpoints.length > 0 && (
            <Button
              size="sm"
              variant="secondary"
              loading={exporting === "top-endpoints"}
              onClick={() => handleExport("top-endpoints")}
            >
              <Download className="h-3.5 w-3.5" />
              Export CSV
            </Button>
          )}
        </CardHeader>
        <CardBody className="p-0">
          {topEndpoints.length === 0 ? (
            <div className="p-6 text-center text-xs text-graphite-500">No deliveries in this window.</div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-graphite-100 text-graphite-500 dark:border-graphite-800">
                  <th className="px-4 py-2 font-medium">Endpoint</th>
                  <th className="px-4 py-2 font-medium">Deliveries</th>
                  <th className="px-4 py-2 font-medium">Success rate</th>
                  <th className="px-4 py-2 font-medium">Avg latency</th>
                </tr>
              </thead>
              <tbody>
                {topEndpoints.map((ep) => {
                  const rate = ep.success_rate ?? 0;
                  const color = rate >= 0.95 ? "green" : rate >= 0.8 ? "amber" : "red";
                  return (
                    <tr key={ep.endpoint_id} className="border-b border-graphite-50 last:border-0 dark:border-graphite-800/60">
                      <td className="px-4 py-2 text-graphite-950 dark:text-graphite-50">{ep.name}</td>
                      <td className="tabular px-4 py-2">{ep.delivery_count}</td>
                      <td className="px-4 py-2">
                        <StatusDot color={color} label={`${(rate * 100).toFixed(1)}%`} />
                      </td>
                      <td className="tabular px-4 py-2">{ep.avg_latency_ms != null ? `${Math.round(ep.avg_latency_ms)}ms` : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function UsageBar({ label, current, max }: { label: string; current: number; max: number | null }) {
  const pct = max ? Math.min(100, (current / max) * 100) : 0;
  const color = pct >= 100 ? "bg-signal-red" : pct >= 80 ? "bg-signal-amber" : "bg-signal-green";

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-graphite-600 dark:text-graphite-400">{label}</span>
        <span className="tabular text-graphite-950 dark:text-graphite-50">
          {current}
          {max != null ? ` / ${max}` : " / unlimited"}
        </span>
      </div>
      {max != null && (
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-graphite-100 dark:bg-graphite-800">
          <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}

function EmptyChartState() {
  return (
    <div className="flex h-[220px] flex-col items-center justify-center gap-2 text-center">
      <StatusDot color="gray" size="md" pulse />
      <p className="text-xs text-graphite-500">No deliveries in this window yet.</p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-2 text-center">
      <StatusDot color="red" size="md" />
      <p className="text-xs text-graphite-600 dark:text-graphite-400">{message}</p>
    </div>
  );
}
