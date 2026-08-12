"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Sidebar } from "@/components/nav/sidebar";
import { Header } from "@/components/nav/header";
import { CommandPaletteProvider } from "@/lib/command-palette-context";
import { CommandPalette } from "@/components/command-palette/command-palette";
import { Loader2 } from "lucide-react";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !me) {
      router.replace("/login");
    }
  }, [loading, me, router]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-graphite-50 dark:bg-graphite-950">
        <Loader2 className="h-5 w-5 animate-spin text-graphite-400" />
      </div>
    );
  }

  if (!me) return null;

  return (
    <CommandPaletteProvider>
      <div className="flex h-screen overflow-hidden bg-[var(--bg-app)]">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Header />
          <main className="flex-1 overflow-y-auto px-6 py-5">{children}</main>
        </div>
      </div>
      <CommandPalette />
    </CommandPaletteProvider>
  );
}
