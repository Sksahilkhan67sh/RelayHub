import { ParsedArgs, flagString } from "../args.js";
import { getClient, run } from "../client.js";
import { printTable, printJson, color } from "../output.js";

export async function analyticsCommand(args: ParsedArgs): Promise<void> {
  await run(async () => {
    const client = getClient({ apiKey: flagString(args.flags, "api-key"), baseUrl: flagString(args.flags, "base-url") });
    const view = args.positionals[0] ?? "summary";
    const range = {
      environment: flagString(args.flags, "environment"),
      start_date: flagString(args.flags, "start-date"),
      end_date: flagString(args.flags, "end-date"),
    };

    switch (view) {
      case "summary": {
        const summary = await client.analytics.summary(range);
        if (args.flags.json) return printJson(summary);
        console.log(`${color.bold("Total events:")}     ${summary.total_events}`);
        console.log(`${color.bold("Total deliveries:")} ${summary.total_deliveries}`);
        console.log(`${color.bold("Success rate:")}     ${(summary.success_rate * 100).toFixed(1)}%`);
        console.log(`${color.bold("p50 latency:")}      ${summary.p50_latency_ms ?? "-"}ms`);
        console.log(`${color.bold("p95 latency:")}      ${summary.p95_latency_ms ?? "-"}ms`);
        console.log(`${color.bold("p99 latency:")}      ${summary.p99_latency_ms ?? "-"}ms`);
        return;
      }
      case "top-endpoints": {
        const top = await client.analytics.topEndpoints(range);
        if (args.flags.json) return printJson(top);
        printTable(
          ["ENDPOINT", "DELIVERIES", "FAILURE RATE"],
          top.map((t) => [t.endpoint_name, String(t.delivery_count), `${(t.failure_rate * 100).toFixed(1)}%`])
        );
        return;
      }
      case "health": {
        const health = await client.analytics.endpointHealth();
        if (args.flags.json) return printJson(health);
        printTable(
          ["ENDPOINT", "STATUS", "CONSECUTIVE FAILURES"],
          health.map((h) => [h.endpoint_name, h.health_status, String(h.consecutive_failure_count)])
        );
        return;
      }
      default:
        console.log("Usage: relay analytics <summary|top-endpoints|health> [--environment ...] [--start-date ...] [--end-date ...]");
    }
  });
}
