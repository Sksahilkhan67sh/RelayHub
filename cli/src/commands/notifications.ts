import { ParsedArgs, flagString, flagBoolean } from "../args.js";
import { getClient, run } from "../client.js";
import { printTable, printJson, success, error, confirm } from "../output.js";

/**
 * "Notifications" maps to RelayHub's alert rules (/v1/alerts/*) -- Slack,
 * Discord, webhook, or email notifications fired on a threshold condition
 * (endpoint down, DLQ spike, high latency, etc). See sdks/node/README.md and
 * docs/api/notifications.md for the same note.
 */
export async function notificationsCommand(args: ParsedArgs): Promise<void> {
  await run(async () => {
    const client = getClient({ apiKey: flagString(args.flags, "api-key"), baseUrl: flagString(args.flags, "base-url") });
    const action = args.positionals[0] ?? "list";

    switch (action) {
      case "list": {
        const rules = await client.notifications.listRules();
        if (args.flags.json) return printJson(rules);
        printTable(
          ["ID", "CONDITION", "SEVERITY", "CHANNEL", "ENABLED"],
          rules.map((r) => [r.id, r.condition_type, r.severity, r.channel, r.is_enabled ? "yes" : "no"])
        );
        return;
      }
      case "create": {
        const conditionType = flagString(args.flags, "condition");
        const channel = flagString(args.flags, "channel");
        if (!conditionType || !channel) {
          return error("Usage: relay notifications create --condition <type> --channel slack|discord|webhook|email --channel-config '<json>' [--severity info|warning|critical]");
        }
        const channelConfigRaw = flagString(args.flags, "channel-config");
        const rule = await client.notifications.createRule({
          condition_type: conditionType,
          severity: (flagString(args.flags, "severity") as "info" | "warning" | "critical" | undefined) ?? "warning",
          channel,
          channel_config: channelConfigRaw ? JSON.parse(channelConfigRaw) : {},
        });
        success(`Created alert rule ${rule.id}`);
        return;
      }
      case "test": {
        const id = args.positionals[1];
        if (!id) return error("Usage: relay notifications test <ruleId>");
        const result = await client.notifications.testRule(id);
        if (result.delivery_status === "sent" || result.delivery_status === "success") {
          success(`Test notification sent (status: ${result.delivery_status})`);
        } else {
          error(`Test notification failed: ${result.delivery_status}${result.delivery_error ? " -- " + result.delivery_error : ""}`);
        }
        return;
      }
      case "delete": {
        const id = args.positionals[1];
        if (!id) return error("Usage: relay notifications delete <ruleId>");
        if (!flagBoolean(args.flags, "yes") && !(await confirm(`Delete alert rule ${id}?`))) return;
        await client.notifications.deleteRule(id);
        success(`Deleted alert rule ${id}`);
        return;
      }
      case "history": {
        const events = await client.notifications.history();
        if (args.flags.json) return printJson(events);
        printTable(
          ["ID", "CONDITION", "SEVERITY", "TRIGGERED", "DELIVERY STATUS"],
          events.map((e) => [e.id, e.condition_type, e.severity, e.triggered_at, e.delivery_status])
        );
        return;
      }
      default:
        error(`Unknown subcommand: notifications ${action}`);
        console.log("Usage: relay notifications <list|create|test|delete|history> [args]");
    }
  });
}
