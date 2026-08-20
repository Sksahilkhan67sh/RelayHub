"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export type DateRangePreset =
  | "today"
  | "yesterday"
  | "last3days"
  | "lastweek"
  | "last10days"
  | "overall"
  | "custom";

export interface DateRange {
  preset: DateRangePreset;
  /** ISO start of window, or null for "overall" (no lower bound). */
  start: string | null;
  /** ISO end of window (always "now" except for a custom range's chosen end date). */
  end: string | null;
  label: string;
}

const PRESETS: { id: DateRangePreset; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "yesterday", label: "Yesterday" },
  { id: "last3days", label: "Last 3 days" },
  { id: "lastweek", label: "Last week" },
  { id: "last10days", label: "Last 10 days" },
  { id: "overall", label: "Overall" },
  { id: "custom", label: "Custom" },
];

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function endOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59, 999);
}

function daysAgo(n: number): Date {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d;
}

/** Resolves a preset (or explicit custom dates) into the {start, end, label} the
 * dashboard's analytics calls need. "Overall" returns null bounds, which means
 * "all-time" to the analytics endpoints (they treat missing start/end as no filter). */
export function resolvePreset(preset: DateRangePreset, customStart?: string, customEnd?: string): DateRange {
  const now = new Date();

  switch (preset) {
    case "today":
      return { preset, start: startOfDay(now).toISOString(), end: now.toISOString(), label: "Today" };
    case "yesterday": {
      const y = daysAgo(1);
      return { preset, start: startOfDay(y).toISOString(), end: endOfDay(y).toISOString(), label: "Yesterday" };
    }
    case "last3days":
      return { preset, start: startOfDay(daysAgo(2)).toISOString(), end: now.toISOString(), label: "Last 3 days" };
    case "lastweek":
      return { preset, start: startOfDay(daysAgo(6)).toISOString(), end: now.toISOString(), label: "Last 7 days" };
    case "last10days":
      return { preset, start: startOfDay(daysAgo(9)).toISOString(), end: now.toISOString(), label: "Last 10 days" };
    case "overall":
      return { preset, start: null, end: null, label: "Overall" };
    case "custom": {
      if (!customStart || !customEnd) {
        // Not enough info yet to resolve -- caller should keep the previous range
        // until both custom dates are picked.
        return { preset, start: null, end: null, label: "Custom" };
      }
      const s = startOfDay(new Date(customStart));
      const e = endOfDay(new Date(customEnd));
      return { preset, start: s.toISOString(), end: e.toISOString(), label: `${customStart} \u2192 ${customEnd}` };
    }
  }
}

export function DateRangeFilter({
  value,
  onChange,
}: {
  value: DateRangePreset;
  onChange: (range: DateRange) => void;
}) {
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");

  function selectPreset(preset: DateRangePreset) {
    if (preset === "custom") {
      // Wait for the user to actually pick both dates before firing a change --
      // resolvePreset("custom") with nothing picked yet is a no-op range.
      onChange(resolvePreset("custom", customStart, customEnd));
      return;
    }
    onChange(resolvePreset(preset));
  }

  function applyCustomRange() {
    if (!customStart || !customEnd) return;
    onChange(resolvePreset("custom", customStart, customEnd));
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p.id}
            onClick={() => selectPreset(p.id)}
            className={`rounded-sm px-2.5 py-1 text-xs font-medium transition-colors ${
              value === p.id
                ? "bg-signal-amber text-white"
                : "bg-graphite-100 text-graphite-600 dark:bg-graphite-800 dark:text-graphite-400"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {value === "custom" && (
        <div className="flex items-center gap-1.5">
          <Input
            type="date"
            value={customStart}
            onChange={(e) => setCustomStart(e.target.value)}
            className="h-8 w-[140px] text-xs"
            aria-label="Custom range start date"
          />
          <span className="text-xs text-graphite-500">to</span>
          <Input
            type="date"
            value={customEnd}
            onChange={(e) => setCustomEnd(e.target.value)}
            className="h-8 w-[140px] text-xs"
            aria-label="Custom range end date"
          />
          <Button size="sm" variant="secondary" onClick={applyCustomRange} disabled={!customStart || !customEnd}>
            Apply
          </Button>
        </div>
      )}
    </div>
  );
}
