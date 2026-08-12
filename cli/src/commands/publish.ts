import { ParsedArgs, flagString } from "../args.js";
import { getClient, run } from "../client.js";
import { printJson, success, error } from "../output.js";

export async function publishCommand(args: ParsedArgs): Promise<void> {
  await run(async () => {
    const client = getClient({ apiKey: flagString(args.flags, "api-key"), baseUrl: flagString(args.flags, "base-url") });
    const event = args.positionals[0];
    if (!event) return error("Usage: relay publish <event.type> [--payload '<json>'] [--environment test|live] [--idempotency-key <key>]");

    const payloadRaw = flagString(args.flags, "payload");
    let payload: Record<string, unknown> | undefined;
    if (payloadRaw) {
      try {
        payload = JSON.parse(payloadRaw);
      } catch {
        return error("--payload must be valid JSON, e.g. --payload '{\"order_id\":\"ord_123\"}'");
      }
    }

    const result = await client.events.publish(
      { event, payload, environment: flagString(args.flags, "environment") as "test" | "live" | undefined },
      { idempotencyKey: flagString(args.flags, "idempotency-key") }
    );
    success(`Published ${event} -- event ${result.id}, ${result.delivery_jobs.length} delivery job(s) queued`);
    if (args.flags.json) printJson(result);
  });
}
