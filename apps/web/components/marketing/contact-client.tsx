"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { LifeBuoy, Briefcase, Bug, Lightbulb, BookOpen, ScrollText, Newspaper, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const REASONS = [
  { value: "support", label: "Support", address: "support@relayhub.dev", icon: LifeBuoy, blurb: "Something's not working the way it should." },
  { value: "sales", label: "Sales", address: "sales@relayhub.dev", icon: Briefcase, blurb: "Questions about Enterprise plans or pricing." },
  { value: "bug", label: "Bug report", address: "support@relayhub.dev", icon: Bug, blurb: "Found something broken? Tell us exactly what happened." },
  { value: "feature", label: "Feature request", address: "product@relayhub.dev", icon: Lightbulb, blurb: "Tell us what RelayHub is missing." },
] as const;

const RESOURCES = [
  { href: "/docs", label: "Documentation", icon: BookOpen },
  { href: "/changelog", label: "Changelog", icon: ScrollText },
  { href: "/blog", label: "Blog", icon: Newspaper },
  { href: "/status", label: "System status", icon: Activity },
];

export function ContactClient() {
  const [reason, setReason] = useState<(typeof REASONS)[number]["value"]>("support");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");

  const active = REASONS.find((r) => r.value === reason) ?? REASONS[0];

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const subject = `[${active.label}] ${name ? `from ${name}` : "Website contact form"}`;
    const body = `${message}\n\n—\n${name} <${email}>`;
    window.location.href = `mailto:${active.address}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  }

  return (
    <div className="mx-auto max-w-6xl px-5 py-16 sm:py-20">
      <div className="max-w-2xl">
        <p className="text-xs font-semibold uppercase tracking-wider text-signal-amber">Contact</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-graphite-950 sm:text-5xl dark:text-graphite-50">Talk to a human</h1>
        <p className="mt-4 text-[15px] leading-relaxed text-graphite-600 dark:text-graphite-400">
          Pick what this is about below -- submitting opens your email client with the right address and subject filled
          in, so it lands directly in the right inbox.
        </p>
      </div>

      <div className="mt-12 grid gap-10 lg:grid-cols-[1fr_1.1fr]">
        <div className="grid grid-cols-2 gap-3">
          {REASONS.map((r) => (
            <button
              key={r.value}
              type="button"
              onClick={() => setReason(r.value)}
              className={`flex flex-col items-start gap-2 rounded-md border p-4 text-left transition-colors ${
                reason === r.value
                  ? "border-signal-amber bg-signal-amber-soft/40"
                  : "border-graphite-100 hover:border-graphite-200 dark:border-graphite-800 dark:hover:border-graphite-700"
              }`}
            >
              <r.icon className="h-4 w-4 text-signal-amber" />
              <span className="text-sm font-medium text-graphite-950 dark:text-graphite-50">{r.label}</span>
              <span className="text-xs text-graphite-500">{r.blurb}</span>
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
          <Input label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-graphite-700 dark:text-graphite-200">Message</label>
            <textarea
              required
              rows={6}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="rounded border border-graphite-200 bg-white px-3 py-2 text-sm text-graphite-950 outline-none focus-visible:ring-2 focus-visible:ring-signal-amber dark:border-graphite-700 dark:bg-graphite-900 dark:text-graphite-50"
            />
          </div>
          <Button type="submit" size="md" className="w-fit">
            Send to {active.address}
          </Button>
        </form>
      </div>

      <div className="mt-20 border-t border-graphite-100 pt-10 dark:border-graphite-800">
        <h2 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Community &amp; resources</h2>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {RESOURCES.map((r) => (
            <Link
              key={r.href}
              href={r.href}
              className="flex items-center gap-2.5 rounded-md border border-graphite-100 px-4 py-3 text-sm text-graphite-700 hover:border-graphite-200 hover:text-graphite-950 dark:border-graphite-800 dark:text-graphite-300 dark:hover:border-graphite-700 dark:hover:text-graphite-50"
            >
              <r.icon className="h-4 w-4 text-signal-amber" />
              {r.label}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
