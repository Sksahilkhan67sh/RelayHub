import { ParsedArgs, flagString } from "../args.js";
import { getClient, run } from "../client.js";
import { printTable, printJson, color, info } from "../output.js";

export async function billingCommand(args: ParsedArgs): Promise<void> {
  await run(async () => {
    const client = getClient({ apiKey: flagString(args.flags, "api-key"), baseUrl: flagString(args.flags, "base-url") });
    const view = args.positionals[0] ?? "usage";

    switch (view) {
      case "plans": {
        const plans = await client.billing.listPlans();
        if (args.flags.json) return printJson(plans);
        printTable(
          ["TIER", "NAME", "PRICE", "MAX DELIVERIES/MO", "RETENTION"],
          plans.map((p) => [p.tier, p.name, `$${(p.price_cents / 100).toFixed(0)}`, String(p.max_deliveries_per_month), `${p.log_retention_days}d`])
        );
        return;
      }
      case "subscription": {
        printJson(await client.billing.getSubscription());
        return;
      }
      case "usage": {
        const usage = await client.billing.getUsage();
        if (args.flags.json) return printJson(usage);
        console.log(`${color.bold("Used:")} ${usage.delivery_count} / ${usage.max_deliveries_per_month ?? "unlimited"} (${usage.percent_used !== null ? usage.percent_used.toFixed(1) + "%" : "n/a"})`);
        return;
      }
      case "invoices": {
        const invoices = await client.billing.listInvoices();
        if (args.flags.json) return printJson(invoices);
        printTable(
          ["ID", "AMOUNT", "STATUS", "DATE"],
          invoices.map((i) => [i.id, `$${(i.amount_cents / 100).toFixed(2)}`, i.status, i.created_at])
        );
        return;
      }
      case "portal": {
        const returnUrl = flagString(args.flags, "return-url") ?? "https://app.relayhub.dev/settings/billing";
        const session = await client.billing.createPortalSession({ return_url: returnUrl });
        info(`Open this URL to manage billing: ${session.portal_url}`);
        return;
      }
      default:
        console.log("Usage: relay billing <plans|subscription|usage|invoices|portal>");
    }
  });
}
