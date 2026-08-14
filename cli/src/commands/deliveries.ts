import { ParsedArgs, flagString, flagNumber } from "../args.js";
import { getClient, run } from "../client.js";
import { printTable, printJson, error } from "../output.js";
import type { DeliveryStatus } from "relayhub-sdk";

export async function deliveriesCommand(args: ParsedArgs): Promise<void> {
  await run(async () => {
    const client = getClient({ apiKey: flagString(args.flags, "api-key"), baseUrl: flagString(args.flags, "base-url") });
    const action = args.positionals[0] ?? "list";

    if (action === "get") {
      const id = args.positionals[1];
      if (!id) return error("Usage: relay deliveries get <jobId>");
      printJson(await client.deliveries.get(id));
      return;
    }

    // "list" filters the searchable delivery log (GET /v1/logs) -- see docs/api/deliveries.md.
    const statusFlag = flagString(args.flags, "status");
    const logs = await client.deliveries.searchLogs({
      endpoint_id: flagString(args.flags, "endpoint-id"),
      status: statusFlag ? (statusFlag.split(",") as DeliveryStatus[]) : undefined,
      event_type: flagString(args.flags, "event-type"),
      environment: flagString(args.flags, "environment"),
      limit: flagNumber(args.flags, "limit") ?? 20,
      offset: flagNumber(args.flags, "offset") ?? 0,
    });

    if (args.flags.json) return printJson(logs);
    printTable(
      ["ID", "EVENT", "ENDPOINT", "STATUS", "ATTEMPT", "QUEUED"],
      logs.map((l) => [l.id, l.event_type, l.endpoint_id, l.status, String(l.attempt_number), l.queued_at])
    );
  });
}
