"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  KeyRound,
  Webhook,
  Zap,
  Send,
  RotateCcw,
  Inbox,
  BarChart3,
  ScrollText,
  Bell,
  Gauge,
  CreditCard,
  Users,
  Settings,
  ShieldCheck,
  LayoutGrid,
  Building2,
  Flag,
  AlertTriangle,
  FileSearch,
  Newspaper,
  Briefcase,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { RelayHubMark } from "@/components/ui/logo";
import { useAuth } from "@/lib/auth-context";

export const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/api-keys", label: "API Keys", icon: KeyRound },
  { href: "/endpoints", label: "Endpoints", icon: Webhook },
  { href: "/events", label: "Events", icon: Zap },
  { href: "/deliveries", label: "Deliveries", icon: Send },
  { href: "/retry-queue", label: "Retry Queue", icon: RotateCcw },
  { href: "/dlq", label: "Dead Letter Queue", icon: Inbox },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/logs", label: "Logs", icon: ScrollText },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/usage", label: "Usage", icon: Gauge },
  { href: "/billing", label: "Billing", icon: CreditCard },
] as const;

export const SETTINGS_ITEMS = [
  { href: "/settings/team", label: "Team", icon: Users },
  { href: "/settings/organization", label: "Organization", icon: Settings },
  { href: "/settings/audit-logs", label: "Audit Logs", icon: ShieldCheck },
] as const;

export const ADMIN_ITEMS = [
  { href: "/admin", label: "Overview", icon: LayoutGrid },
  { href: "/admin/organizations", label: "Organizations", icon: Building2 },
  { href: "/admin/feature-flags", label: "Feature Flags", icon: Flag },
  { href: "/admin/abuse-reports", label: "Abuse Reports", icon: AlertTriangle },
  { href: "/admin/logs", label: "Global Logs", icon: FileSearch },
  { href: "/admin/blog", label: "Blog", icon: Newspaper },
  { href: "/admin/careers", label: "Careers", icon: Briefcase },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const { me } = useAuth();

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-graphite-800 bg-[var(--sidebar-bg)] py-4">
      <div className="flex items-center gap-2 px-4 pb-4">
        <RelayHubMark />
        <span className="text-sm font-semibold text-white">RelayHub</span>
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.href} item={item} active={pathname?.startsWith(item.href)} />
        ))}

        <div className="mt-4 px-2 pb-1 text-[10px] font-semibold uppercase tracking-wide text-graphite-600">Settings</div>
        {SETTINGS_ITEMS.map((item) => (
          <NavLink key={item.href} item={item} active={pathname?.startsWith(item.href)} />
        ))}

        {me?.user.is_platform_admin && (
          <>
            <div className="mt-4 px-2 pb-1 text-[10px] font-semibold uppercase tracking-wide text-graphite-600">Admin</div>
            {ADMIN_ITEMS.map((item) => (
              <NavLink key={item.href} item={item} active={pathname === item.href || (item.href !== "/admin" && pathname?.startsWith(item.href))} />
            ))}
          </>
        )}
      </nav>
    </aside>
  );
}

function NavLink({
  item,
  active,
}: {
  item: { href: string; label: string; icon: React.ComponentType<{ className?: string }> };
  active?: boolean;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-2.5 rounded px-2.5 py-1.5 text-[13px] transition-colors",
        active ? "bg-graphite-800 text-white" : "text-[var(--sidebar-text)] hover:bg-graphite-800/60 hover:text-white"
      )}
    >
      <Icon className="h-[15px] w-[15px] shrink-0" />
      {item.label}
    </Link>
  );
}
