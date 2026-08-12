"use client";

import { useAuth } from "@/lib/auth-context";
import { ShieldAlert } from "lucide-react";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();

  if (loading) return null;

  if (!me?.user.is_platform_admin) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-24 text-center">
        <ShieldAlert className="h-8 w-8 text-graphite-400" />
        <h2 className="text-sm font-semibold text-graphite-950 dark:text-graphite-50">Platform admin access required</h2>
        <p className="max-w-xs text-xs text-graphite-600 dark:text-graphite-400">
          This area is restricted to RelayHub platform administrators, not organization owners/admins.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
