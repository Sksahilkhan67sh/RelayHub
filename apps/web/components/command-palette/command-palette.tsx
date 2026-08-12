"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Clock, CornerDownLeft } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useCommandPalette } from "@/lib/command-palette-context";
import { buildPageCommands, buildQuickActionCommands, fetchSearchCommands, type PaletteCommand } from "@/lib/commands";
import { fuzzyFilterAndSort } from "@/lib/fuzzy";
import { cn } from "@/lib/cn";

const RECENTS_KEY = "relayhub_recent_commands";
const MAX_RECENTS = 5;

function loadRecents(): PaletteCommand[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(RECENTS_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Icons aren't JSON-serializable, so recents are stored without one and given
    // the Clock icon back at load time (the "Recent" group always renders Clock
    // regardless, but this keeps the PaletteCommand shape honest end to end).
    return parsed
      .filter((c): c is Omit<PaletteCommand, "icon"> => typeof c?.id === "string" && typeof c?.href === "string")
      .map((c) => ({ ...c, icon: Clock }));
  } catch {
    return [];
  }
}

function pushRecent(command: PaletteCommand) {
  const current = loadRecents().filter((c) => c.id !== command.id);
  const { icon: _icon, ...stored } = command;
  const next = [stored, ...current.map(({ icon: _i, ...rest }) => rest)].slice(0, MAX_RECENTS);
  window.localStorage.setItem(RECENTS_KEY, JSON.stringify(next));
}

export function CommandPalette() {
  const { open, closePalette, togglePalette } = useCommandPalette();
  const { me } = useAuth();
  const router = useRouter();

  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [searchResults, setSearchResults] = useState<PaletteCommand[]>([]);
  const [searching, setSearching] = useState(false);
  const [recents, setRecents] = useState<PaletteCommand[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const isPlatformAdmin = !!me?.user.is_platform_admin;

  const staticCommands = useMemo(
    () => [...buildQuickActionCommands(), ...buildPageCommands(isPlatformAdmin)],
    [isPlatformAdmin]
  );

  // Global Cmd/Ctrl+K, from anywhere in the dashboard.
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        togglePalette();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [togglePalette]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      setRecents(loadRecents());
      const id = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(id);
    }
  }, [open]);

  // Debounced live search across real API resources.
  useEffect(() => {
    if (!open || query.trim().length < 2) {
      setSearchResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    const handle = window.setTimeout(async () => {
      const results = await fetchSearchCommands(query, isPlatformAdmin);
      setSearchResults(results);
      setSearching(false);
    }, 200);
    return () => window.clearTimeout(handle);
  }, [query, open, isPlatformAdmin]);

  const filteredStatic = useMemo(
    () => fuzzyFilterAndSort(staticCommands, query.trim(), (c) => `${c.label} ${c.group}`),
    [staticCommands, query]
  );

  const groups = useMemo(() => {
    if (!query.trim()) {
      const g: { name: string; items: PaletteCommand[] }[] = [];
      if (recents.length > 0) g.push({ name: "Recent", items: recents });
      g.push({ name: "Quick actions", items: filteredStatic.filter((c) => c.group === "Quick actions") });
      g.push({ name: "Pages", items: filteredStatic.filter((c) => c.group === "Pages") });
      const rest = filteredStatic.filter((c) => c.group !== "Quick actions" && c.group !== "Pages");
      const restByGroup = new Map<string, PaletteCommand[]>();
      for (const c of rest) restByGroup.set(c.group, [...(restByGroup.get(c.group) ?? []), c]);
      for (const [name, items] of restByGroup) g.push({ name, items });
      return g.filter((grp) => grp.items.length > 0);
    }

    const byGroup = new Map<string, PaletteCommand[]>();
    for (const c of [...filteredStatic, ...searchResults]) {
      byGroup.set(c.group, [...(byGroup.get(c.group) ?? []), c]);
    }
    // Stable, sensible group ordering.
    const order = ["Quick actions", "Pages", "Settings", "Admin", "Endpoints", "API Keys", "Events", "Deliveries", "Team", "Alerts", "Organizations"];
    return order.map((name) => ({ name, items: byGroup.get(name) ?? [] })).filter((g) => g.items.length > 0);
  }, [query, filteredStatic, searchResults, recents]);

  const flatItems = useMemo(() => groups.flatMap((g) => g.items), [groups]);

  useEffect(() => {
    setActiveIndex(0);
  }, [flatItems.length, query]);

  function execute(command: PaletteCommand) {
    pushRecent(command);
    closePalette();
    router.push(command.href);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      closePalette();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (flatItems.length ? (i + 1) % flatItems.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (flatItems.length ? (i - 1 + flatItems.length) % flatItems.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const target = flatItems[activeIndex];
      if (target) execute(target);
    }
  }

  useEffect(() => {
    const activeEl = listRef.current?.querySelector<HTMLElement>(`[data-index="${activeIndex}"]`);
    activeEl?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  if (!open) return null;

  let runningIndex = -1;

  const activeCommand = flatItems[activeIndex];

  return (
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center bg-graphite-950/40 px-4 pt-[12vh]"
      role="presentation"
      onClick={closePalette}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
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
            placeholder="Search pages, endpoints, events, team..."
            className="h-11 w-full bg-transparent text-sm text-graphite-950 outline-none placeholder:text-graphite-400 dark:text-graphite-50"
            aria-label="Command palette search"
            aria-activedescendant={activeCommand ? `cmd-${activeCommand.id}` : undefined}
            role="combobox"
            aria-expanded="true"
            aria-controls="command-palette-list"
          />
          <kbd className="shrink-0 rounded border border-graphite-200 px-1.5 py-0.5 text-[10px] text-graphite-400 dark:border-graphite-700">
            ESC
          </kbd>
        </div>

        <div ref={listRef} id="command-palette-list" role="listbox" className="max-h-96 overflow-y-auto py-1.5">
          {groups.length === 0 && !searching && (
            <div className="px-4 py-8 text-center text-xs text-graphite-500">No matches for &ldquo;{query}&rdquo;</div>
          )}
          {groups.map((group) => (
            <div key={group.name} className="px-1.5 py-1">
              <div className="px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-graphite-500">{group.name}</div>
              {group.items.map((item) => {
                runningIndex++;
                const idx = runningIndex;
                const Icon = group.name === "Recent" ? Clock : item.icon;
                const active = idx === activeIndex;
                return (
                  <button
                    key={item.id}
                    id={`cmd-${item.id}`}
                    data-index={idx}
                    role="option"
                    aria-selected={active}
                    onMouseEnter={() => setActiveIndex(idx)}
                    onClick={() => execute(item)}
                    className={cn(
                      "flex w-full items-center gap-2.5 rounded px-2.5 py-1.5 text-left text-xs",
                      active ? "bg-signal-amber-soft text-[#8A5D1F]" : "text-graphite-700 dark:text-graphite-200"
                    )}
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0 text-graphite-400" />
                    <span className="flex-1 truncate">
                      <span className="font-medium text-graphite-950 dark:text-graphite-50">{item.label}</span>
                      {item.sublabel && <span className="ml-1.5 text-graphite-500">{item.sublabel}</span>}
                    </span>
                    {active && <CornerDownLeft className="h-3 w-3 shrink-0 text-graphite-400" />}
                  </button>
                );
              })}
            </div>
          ))}
          {searching && <div className="px-4 py-3 text-center text-xs text-graphite-500">Searching...</div>}
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
  );
}
