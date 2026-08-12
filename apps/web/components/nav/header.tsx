"use client";

import { useState } from "react";
import { ChevronDown, LogOut, Command, Sun, Moon } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useTheme } from "@/lib/theme-context";
import { useCommandPalette } from "@/lib/command-palette-context";

export function Header() {
  const { me, logout } = useAuth();
  const { resolvedTheme, toggleTheme } = useTheme();
  const { openPalette } = useCommandPalette();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-10 flex h-12 shrink-0 items-center justify-between border-b border-graphite-100 bg-white/90 px-5 backdrop-blur dark:border-graphite-800 dark:bg-graphite-950/90">
      <div className="flex items-center gap-1.5 text-[13px] font-medium text-graphite-950 dark:text-graphite-50">
        {me?.organization.name ?? "..."}
        <ChevronDown className="h-3.5 w-3.5 text-graphite-400" />
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={toggleTheme}
          className="flex h-7 w-7 items-center justify-center rounded border border-graphite-200 text-graphite-600 hover:bg-graphite-50 dark:border-graphite-700 dark:text-graphite-400 dark:hover:bg-graphite-800"
          aria-label={resolvedTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={resolvedTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {resolvedTheme === "dark" ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
        </button>

        <button
          onClick={openPalette}
          className="flex items-center gap-1.5 rounded border border-graphite-200 px-2 py-1 text-xs text-graphite-600 hover:bg-graphite-50 dark:border-graphite-700 dark:text-graphite-400 dark:hover:bg-graphite-800"
          aria-label="Open command palette"
        >
          <Command className="h-3 w-3" />
          <span className="tabular">K</span>
        </button>

        <div className="relative">
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex h-7 w-7 items-center justify-center rounded-full bg-signal-amber text-xs font-semibold text-white"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            {me?.user.full_name?.[0]?.toUpperCase() ?? "?"}
          </button>
          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-9 w-48 rounded border border-graphite-100 bg-white py-1 shadow-lg dark:border-graphite-800 dark:bg-graphite-900"
            >
              <div className="border-b border-graphite-100 px-3 py-2 text-xs text-graphite-600 dark:border-graphite-800 dark:text-graphite-400">
                {me?.user.email}
              </div>
              <button
                role="menuitem"
                onClick={() => logout()}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-graphite-700 hover:bg-graphite-50 dark:text-graphite-200 dark:hover:bg-graphite-800"
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
