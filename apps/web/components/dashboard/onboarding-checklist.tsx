"use client";

/**
 * First-run onboarding checklist for the dashboard.
 *
 * There is no backend "onboarding" resource -- no persisted completion flag,
 * no onboarding endpoint. Deliberately: completion is derived entirely from
 * data the backend already has (does this org have an API key / endpoint /
 * event yet?), using the same list endpoints the API Keys, Endpoints, and
 * Events pages already call. Dismissal is a client-side-only preference
 * (localStorage, scoped to the org id), the same pattern already used for
 * token storage in lib/api-client.ts -- not a fabricated backend field.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Circle, KeyRound, Webhook, Zap, X } from "lucide-react";
import { api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { ApiKeyOut, EndpointOut, EventOut } from "@/lib/types";

function dismissedKey(orgId: string): string {
  return `relayhub_onboarding_dismissed_${orgId}`;
}

interface StepState {
  key: string;
  label: string;
  description: string;
  href: string;
  icon: typeof KeyRound;
  done: boolean;
}

export function OnboardingChecklist() {
  const { me } = useAuth();
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(true);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [hasEndpoint, setHasEndpoint] = useState(false);
  const [hasEvent, setHasEvent] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    if (!me) return;

    const orgId = me.organization.id;
    if (typeof window !== "undefined" && window.localStorage.getItem(dismissedKey(orgId)) === "1") {
      setDismissed(true);
      setLoading(false);
      return;
    }
    setDismissed(false);

    let cancelled = false;

    async function load() {
      try {
        const [apiKeys, endpoints, events] = await Promise.all([
          api.get<ApiKeyOut[]>("/v1/api-keys"),
          api.get<EndpointOut[]>("/v1/endpoints"),
          api.get<EventOut[]>("/v1/events"),
        ]);
        if (cancelled) return;
        setHasApiKey(apiKeys.length > 0);
        setHasEndpoint(endpoints.length > 0);
        setHasEvent(events.length > 0);
      } catch {
        if (cancelled) return;
        // Fail silent and hide the checklist rather than blocking the dashboard
        // on a non-essential widget.
        setLoadFailed(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [me]);

  if (!me || loading || dismissed || loadFailed) return null;

  const steps: StepState[] = [
    {
      key: "api-key",
      label: "Create an API key",
      description: "Needed to authenticate requests from your app.",
      href: "/api-keys",
      icon: KeyRound,
      done: hasApiKey,
    },
    {
      key: "endpoint",
      label: "Add an endpoint",
      description: "The URL RelayHub delivers webhook events to.",
      href: "/endpoints",
      icon: Webhook,
      done: hasEndpoint,
    },
    {
      key: "event",
      label: "Send a test event",
      description: "Publish an event and watch it deliver.",
      href: "/events",
      icon: Zap,
      done: hasEvent,
    },
  ];

  const allDone = steps.every((s) => s.done);
  const orgId = me.organization.id;

  function dismiss() {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(dismissedKey(orgId), "1");
    }
    setDismissed(true);
  }

  // Once every step is complete, there's nothing left to guide the person
  // through -- auto-dismiss so it doesn't linger as dead chrome.
  if (allDone) {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(dismissedKey(orgId), "1");
    }
    return null;
  }

  return (
    <Card className="relative overflow-hidden">
      <button
        onClick={dismiss}
        aria-label="Dismiss setup checklist"
        className="absolute right-3 top-3 rounded p-1 text-graphite-400 hover:bg-graphite-50 hover:text-graphite-700 dark:hover:bg-graphite-800 dark:hover:text-graphite-200"
      >
        <X className="h-3.5 w-3.5" />
      </button>
      <div className="p-4">
        <h2 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">
          Finish setting up RelayHub
        </h2>
        <p className="mt-0.5 text-xs text-graphite-600 dark:text-graphite-400">
          A few steps to start receiving real webhook deliveries.
        </p>
        <div className="mt-4 flex flex-col gap-2">
          {steps.map((step) => (
            <Link
              key={step.key}
              href={step.href}
              className={cn(
                "flex items-center gap-3 rounded-md border border-graphite-100 px-3 py-2.5 transition-colors dark:border-graphite-800",
                step.done ? "bg-graphite-50 dark:bg-graphite-800/50" : "hover:bg-graphite-50 dark:hover:bg-graphite-800/50"
              )}
            >
              {step.done ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-signal-green" />
              ) : (
                <Circle className="h-4 w-4 shrink-0 text-graphite-300 dark:text-graphite-600" />
              )}
              <step.icon className="h-3.5 w-3.5 shrink-0 text-graphite-400" />
              <div className="min-w-0 flex-1">
                <div
                  className={cn(
                    "text-xs font-medium",
                    step.done
                      ? "text-graphite-500 line-through dark:text-graphite-500"
                      : "text-graphite-950 dark:text-graphite-50"
                  )}
                >
                  {step.label}
                </div>
                <div className="text-xs text-graphite-500 dark:text-graphite-400">{step.description}</div>
              </div>
            </Link>
          ))}
        </div>
        <div className="mt-3 flex justify-end">
          <Button variant="ghost" size="sm" onClick={dismiss}>
            Skip for now
          </Button>
        </div>
      </div>
    </Card>
  );
}
