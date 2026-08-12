import type { LucideIcon } from "lucide-react";
import {
  Plus,
  UserPlus,
  CreditCard,
  BarChart3,
  ScrollText,
  Settings,
  Webhook,
  KeyRound,
  Zap,
  Send,
  Users,
  Bell,
  Building2,
} from "lucide-react";
import { NAV_ITEMS, SETTINGS_ITEMS, ADMIN_ITEMS } from "@/components/nav/sidebar";
import { api } from "@/lib/api-client";
import { fuzzyFilterAndSort } from "@/lib/fuzzy";
import type {
  EndpointOut,
  ApiKeyOut,
  EventOut,
  DeliveryLogEntryOut,
  MemberOut,
  AlertRuleOut,
  AdminOrganizationOut,
} from "@/lib/types";

export interface PaletteCommand {
  id: string;
  label: string;
  sublabel?: string;
  group: string;
  icon: LucideIcon;
  href: string;
}

export function buildPageCommands(isPlatformAdmin: boolean): PaletteCommand[] {
  const commands: PaletteCommand[] = [
    ...NAV_ITEMS.map((item) => ({ id: `page:${item.href}`, label: item.label, group: "Pages", icon: item.icon, href: item.href })),
    ...SETTINGS_ITEMS.map((item) => ({ id: `page:${item.href}`, label: item.label, group: "Settings", icon: item.icon, href: item.href })),
  ];
  if (isPlatformAdmin) {
    commands.push(
      ...ADMIN_ITEMS.map((item) => ({ id: `page:${item.href}`, label: item.label, group: "Admin", icon: item.icon, href: item.href }))
    );
  }
  return commands;
}

export function buildQuickActionCommands(): PaletteCommand[] {
  return [
    { id: "action:create-endpoint", label: "Create Endpoint", group: "Quick actions", icon: Webhook, href: "/endpoints" },
    { id: "action:publish-event", label: "Publish Event", group: "Quick actions", icon: Zap, href: "/events" },
    { id: "action:invite-member", label: "Invite Member", group: "Quick actions", icon: UserPlus, href: "/settings/team" },
    { id: "action:create-api-key", label: "Create API Key", group: "Quick actions", icon: KeyRound, href: "/api-keys" },
    { id: "action:open-billing", label: "Open Billing", group: "Quick actions", icon: CreditCard, href: "/billing" },
    { id: "action:open-analytics", label: "Open Analytics", group: "Quick actions", icon: BarChart3, href: "/analytics" },
    { id: "action:open-logs", label: "Open Logs", group: "Quick actions", icon: ScrollText, href: "/logs" },
    { id: "action:open-settings", label: "Open Settings", group: "Quick actions", icon: Settings, href: "/settings/organization" },
  ];
}

const SEARCH_RESULT_LIMIT_PER_GROUP = 5;

/**
 * Live search across real org data via the existing list endpoints -- results are
 * whatever the API actually returns, filtered/ranked client-side with fuzzyFilterAndSort.
 * No new backend surface, no mock data: entities without their own detail page (API
 * keys, events, alerts) link to the list page they live on rather than a fake route.
 */
export async function fetchSearchCommands(query: string, isPlatformAdmin: boolean): Promise<PaletteCommand[]> {
  const trimmed = query.trim();
  if (trimmed.length < 2) return [];

  const requests: Promise<PaletteCommand[]>[] = [
    api
      .get<EndpointOut[]>("/v1/endpoints")
      .then((items) =>
        fuzzyFilterAndSort(items, trimmed, (e) => `${e.name} ${e.url}`, SEARCH_RESULT_LIMIT_PER_GROUP).map((e) => ({
          id: `endpoint:${e.id}`,
          label: e.name,
          sublabel: e.url,
          group: "Endpoints",
          icon: Webhook,
          href: `/endpoints/${e.id}`,
        }))
      )
      .catch(() => []),
    api
      .get<ApiKeyOut[]>("/v1/api-keys")
      .then((items) =>
        fuzzyFilterAndSort(items, trimmed, (k) => k.name, SEARCH_RESULT_LIMIT_PER_GROUP).map((k) => ({
          id: `api-key:${k.id}`,
          label: k.name,
          sublabel: k.masked_key,
          group: "API Keys",
          icon: KeyRound,
          href: "/api-keys",
        }))
      )
      .catch(() => []),
    api
      .get<EventOut[]>("/v1/events")
      .then((items) =>
        fuzzyFilterAndSort(items, trimmed, (e) => `${e.event} ${e.request_id}`, SEARCH_RESULT_LIMIT_PER_GROUP).map((e) => ({
          id: `event:${e.id}`,
          label: e.event,
          sublabel: e.request_id,
          group: "Events",
          icon: Zap,
          href: "/events",
        }))
      )
      .catch(() => []),
    api
      .get<DeliveryLogEntryOut[]>("/v1/logs?limit=100")
      .then((items) =>
        fuzzyFilterAndSort(items, trimmed, (d) => `${d.event_type} ${d.request_id}`, SEARCH_RESULT_LIMIT_PER_GROUP).map((d) => ({
          id: `delivery:${d.id}`,
          label: d.event_type,
          sublabel: d.status,
          group: "Deliveries",
          icon: Send,
          href: `/deliveries/${d.id}`,
        }))
      )
      .catch(() => []),
    api
      .get<MemberOut[]>("/v1/org/members")
      .then((items) =>
        fuzzyFilterAndSort(items, trimmed, (m) => `${m.full_name} ${m.email}`, SEARCH_RESULT_LIMIT_PER_GROUP).map((m) => ({
          id: `member:${m.user_id}`,
          label: m.full_name,
          sublabel: m.email,
          group: "Team",
          icon: Users,
          href: `/settings/team/${m.user_id}`,
        }))
      )
      .catch(() => []),
    api
      .get<AlertRuleOut[]>("/v1/alerts/rules")
      .then((items) =>
        fuzzyFilterAndSort(items, trimmed, (a) => `${a.condition_type} ${a.channel}`, SEARCH_RESULT_LIMIT_PER_GROUP).map((a) => ({
          id: `alert:${a.id}`,
          label: a.condition_type.replace(/_/g, " "),
          sublabel: `via ${a.channel}`,
          group: "Alerts",
          icon: Bell,
          href: "/alerts",
        }))
      )
      .catch(() => []),
  ];

  if (isPlatformAdmin) {
    requests.push(
      api
        .get<AdminOrganizationOut[]>("/v1/admin/organizations?limit=200")
        .then((items) =>
          fuzzyFilterAndSort(items, trimmed, (o) => `${o.name} ${o.slug}`, SEARCH_RESULT_LIMIT_PER_GROUP).map((o) => ({
            id: `org:${o.id}`,
            label: o.name,
            sublabel: o.slug,
            group: "Organizations",
            icon: Building2,
            href: "/admin/organizations",
          }))
        )
        .catch(() => [])
    );
  }

  const results = await Promise.all(requests);
  return results.flat();
}
