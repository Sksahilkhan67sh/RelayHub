import { ParsedArgs, flagString, flagNumber, flagBoolean } from "../args.js";
import { getClient, run } from "../client.js";
import { printTable, printJson, success, error, confirm } from "../output.js";

export async function dlqCommand(args: ParsedArgs): Promise<void> {
  await run(async () => {
    const client = getClient({ apiKey: flagString(args.flags, "api-key"), baseUrl: flagString(args.flags, "base-url") });
    const action = args.positionals[0] ?? "list";

    switch (action) {
      case "list": {
        const jobs = await client.dlq.list({
          endpoint_id: flagString(args.flags, "endpoint-id"),
          limit: flagNumber(args.flags, "limit") ?? 20,
          offset: flagNumber(args.flags, "offset") ?? 0,
        });
        if (args.flags.json) return printJson(jobs);
        printTable(
          ["ID", "EVENT TYPE", "ENDPOINT", "ATTEMPTS", "LAST ERROR"],
          jobs.map((j) => [j.id, j.event_type, j.endpoint_id, String(j.attempt_number), j.last_error_message ?? "-"])
        );
        return;
      }
      case "get": {
        const id = args.positionals[1];
        if (!id) return error("Usage: relay dlq get <jobId>");
        printJson(await client.dlq.get(id));
        return;
      }
      case "retry": {
        const id = args.positionals[1];
        if (!id) return error("Usage: relay dlq retry <jobId>");
        if (!flagBoolean(args.flags, "yes") && !(await confirm(`Retry dead-lettered delivery ${id}?`))) return;
        const result = await client.dlq.retry(id);
        success(`Retry queued for ${id} -- new status: ${result.status}`);
        return;
      }
      case "discard": {
        const id = args.positionals[1];
        if (!id) return error("Usage: relay dlq discard <jobId>");
        if (!flagBoolean(args.flags, "yes") && !(await confirm(`Permanently discard ${id}? This cannot be undone.`))) return;
        await client.dlq.discard(id);
        success(`Discarded ${id}`);
        return;
      }
      case "export": {
        const csv = await client.dlq.export({ endpoint_id: flagString(args.flags, "endpoint-id") });
        console.log(csv);
        return;
      }
      default:
        error(`Unknown subcommand: dlq ${action}`);
        console.log("Usage: relay dlq <list|get|retry|discard|export> [args]");
    }
  });
}
