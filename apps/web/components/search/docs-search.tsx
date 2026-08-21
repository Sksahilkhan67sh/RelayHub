"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Search, FileText, Braces, Terminal, Package, BookOpen } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { fuzzyFilterAndSort } from "@/lib/fuzzy";
import { DOCS_SEARCH_INDEX, type DocsSearchEntry } from "@/lib/docs-search-index";
import { cn } from "@/lib/cn";

const CATEGORY_ICON: Record<DocsSearchEntry["category"], LucideIcon> = {
  Page: BookOpen,
  Guide: FileText,
  API: Braces,
  CLI: Terminal,
  SDK: Package,
};

const RESULT_LIMIT = 30;

export function DocsSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "/" && !open) {
        const target = e.target as HTMLElement | null;
        const typing = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.isContentEditable;
        if (!typing) {
          e.preventDefault();
          setOpen(true);
        }
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      const id = window.setTimeout(() => inputRef.current?.focus(), 0);
      const previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        window.clearTimeout(id);
        document.body.style.overflow = previousOverflow;
      };
    }
  }, [open]);

  const results = useMemo(() => {
    const trimmed = query.trim();
    if (!trimmed) return DOCS_SEARCH_INDEX.slice(0, RESULT_LIMIT);
    return fuzzyFilterAndSort(DOCS_SEARCH_INDEX, trimmed, (e) => `${e.title} ${e.snippet} ${e.category}`, RESULT_LIMIT);
  }, [query]);

  useEffect(() => {
    setActiveIndex(0);
  }, [results.length, query]);

  useEffect(() => {
    const activeEl = listRef.current?.querySelector<HTMLElement>(`[data-index="${activeIndex}"]`);
    activeEl?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  function close() {
    setOpen(false);
  }

  function navigate(entry: DocsSearchEntry) {
    close();
    router.push(entry.href);
  }

  const dialogRef = useRef<HTMLDivElement>(null);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (results.length ? (i + 1) % results.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (results.length ? (i - 1 + results.length) % results.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const target = results[activeIndex];
      if (target) navigate(target);
    } else if (e.key === "Tab") {
      // Keep focus inside the dialog -- there's no element outside it that
      // should be reachable while it's open.
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>("input, button");
      if (!focusable || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) return;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  const activeEntry = results[activeIndex];

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Search documentation"
        className="flex w-full max-w-[220px] items-center gap-2 rounded-md border border-graphite-200 bg-white px-2.5 py-1.5 text-left text-xs text-graphite-500 transition-colors hover:border-graphite-300 dark:border-graphite-800 dark:bg-graphite-950 dark:text-graphite-400 dark:hover:border-graphite-700"
      >
        <Search className="h-3.5 w-3.5 shrink-0" />
        <span className="flex-1 truncate">Search docs</span>
        <kbd className="shrink-0 rounded border border-graphite-200 px-1 text-[10px] dark:border-graphite-700">/</kbd>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[200] flex items-start justify-center bg-graphite-950/40 px-4 pt-[12vh]"
          role="presentation"
          onClick={close}
        >
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-label="Documentation search"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={handleKeyDown}
            className="flex w-full max-w-lg flex-col overflow-hidden rounded-md border border-graphite-100 bg-white shadow-lg dark:border-graphite-800 dark:bg-graphite-900"
          >
            <div className="flex items-center gap-2 border-b border-graphite-100 px-3 dark:border-graphite-800">
              <Search className="h-4 w-4 shrink-0 text-graphite-400" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search pages, API endpoints, SDK methods, CLI commands..."
                className="h-11 w-full bg-transparent text-sm text-graphite-950 outline-none placeholder:text-graphite-400 dark:text-graphite-50"
                aria-label="Documentation search"
                aria-activedescendant={activeEntry ? `docs-search-${activeEntry.id}` : undefined}
                role="combobox"
                aria-expanded="true"
                aria-controls="docs-search-list"
                aria-autocomplete="list"
              />
              <kbd className="shrink-0 rounded border border-graphite-200 px-1.5 py-0.5 text-[10px] text-graphite-400 dark:border-graphite-700">
                ESC
              </kbd>
            </div>

            <div ref={listRef} id="docs-search-list" role="listbox" className="max-h-96 overflow-y-auto py-1.5">
              {results.length === 0 && (
                <div className="px-4 py-8 text-center text-xs text-graphite-500">
                  {query.trim() ? (
                    <>No results for &ldquo;{query}&rdquo;</>
                  ) : (
                    "Start typing to search the Developers docs"
                  )}
                </div>
              )}
              {results.map((entry, idx) => {
                const Icon = CATEGORY_ICON[entry.category];
                const active = idx === activeIndex;
                const isCurrentPage = entry.href.split("#")[0] === pathname;
                return (
                  <button
                    key={entry.id}
                    id={`docs-search-${entry.id}`}
                    data-index={idx}
                    role="option"
                    aria-selected={active}
                    onMouseEnter={() => setActiveIndex(idx)}
                    onClick={() => navigate(entry)}
                    className={cn(
                      "flex w-full items-start gap-2.5 px-3 py-2 text-left text-xs",
                      active ? "bg-signal-amber-soft text-[#8A5D1F]" : "text-graphite-700 dark:text-graphite-200"
                    )}
                  >
                    <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-graphite-400" />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-1.5">
                        <span className="truncate font-medium text-graphite-950 dark:text-graphite-50">{entry.title}</span>
                        <span className="shrink-0 rounded border border-graphite-200 px-1 text-[9px] uppercase tracking-wide text-graphite-400 dark:border-graphite-700">
                          {entry.category}
                        </span>
                        {isCurrentPage && (
                          <span className="shrink-0 rounded bg-graphite-100 px-1 text-[9px] uppercase tracking-wide text-graphite-500 dark:bg-graphite-800">
                            Current page
                          </span>
                        )}
                      </span>
                      <span className="mt-0.5 block truncate text-graphite-500">{entry.snippet}</span>
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-3 border-t border-graphite-100 px-3 py-1.5 text-[10px] text-graphite-400 dark:border-graphite-800">
              <span className="flex items-center gap-1">
                <kbd className="rounded border border-graphite-200 px-1 dark:border-graphite-700">&uarr;</kbd>
                <kbd className="rounded border border-graphite-200 px-1 dark:border-graphite-700">&darr;</kbd>
                navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="rounded border border-graphite-200 px-1 dark:border-graphite-700">&crarr;</kbd>
                select
              </span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
