"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

export interface CodeTab {
  label: string;
  code: string;
}

export function CodeTabs({ tabs, filename }: { tabs: CodeTab[]; filename?: string }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [copied, setCopied] = useState(false);
  const active = tabs[activeIndex];

  async function handleCopy() {
    if (!active) return;
    try {
      await navigator.clipboard.writeText(active.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API can be unavailable (e.g. insecure context) -- fail quietly,
      // the code is still fully selectable/copyable by hand.
    }
  }

  if (!active) return null;

  return (
    <div className="overflow-hidden rounded-md border border-graphite-800 bg-graphite-950">
      <div className="flex items-center justify-between border-b border-graphite-800 px-2">
        <div className="flex items-center gap-1">
          {tabs.map((tab, i) => (
            <button
              key={tab.label}
              onClick={() => setActiveIndex(i)}
              className={`px-2.5 py-2 font-mono text-[11px] transition-colors ${
                i === activeIndex ? "border-b-2 border-signal-amber text-white" : "text-graphite-500 hover:text-graphite-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          {filename && <span className="font-mono text-[11px] text-graphite-600">{filename}</span>}
          <button
            onClick={handleCopy}
            aria-label="Copy code"
            className="flex items-center gap-1 rounded px-1.5 py-1 text-graphite-500 hover:bg-graphite-800 hover:text-graphite-200"
          >
            {copied ? <Check className="h-3 w-3 text-signal-green" /> : <Copy className="h-3 w-3" />}
          </button>
        </div>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed text-graphite-200">{active.code}</pre>
    </div>
  );
}
