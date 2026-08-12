"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

export function FaqAccordion({ items }: { items: { q: string; a: string }[] }) {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <div className="flex flex-col divide-y divide-graphite-100 border-t border-graphite-100 dark:divide-graphite-800 dark:border-graphite-800">
      {items.map((item, i) => {
        const open = openIndex === i;
        return (
          <div key={item.q}>
            <button
              onClick={() => setOpenIndex(open ? null : i)}
              aria-expanded={open}
              aria-controls={`faq-panel-${i}`}
              className="flex w-full items-center justify-between gap-4 py-4 text-left"
            >
              <span className="text-sm font-medium text-graphite-950 dark:text-graphite-50">{item.q}</span>
              <ChevronDown className={cn("h-4 w-4 shrink-0 text-graphite-400 transition-transform", open && "rotate-180")} />
            </button>
            {open && (
              <p id={`faq-panel-${i}`} className="pb-4 text-[13.5px] leading-relaxed text-graphite-600 dark:text-graphite-400">
                {item.a}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
