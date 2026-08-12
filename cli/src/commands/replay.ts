import { ParsedArgs, flagString, flagBoolean } from "../args.js";
import { getClient, run } from "../client.js";
import { success, error, confirm } from "../output.js";

/**
 * "Replay" is a dead-letter-queue operation in the real API
 * (POST /v1/dlq/{id}/retry) -- there's no separate top-level replay endpoint, so
 * this command is a thin, honestly-labeled alias over `client.dlq.retry`. See
 * docs/api/dlq.md.
 */
export async function replayCommand(args: ParsedArgs): Promise<void> {
  await run(async () => {
    const client = getClient({ apiKey: flagString(args.flags, "api-key"), baseUrl: flagString(args.flags, "base-url") });
    const id = args.positionals[0];
    if (!id) return error("Usage: relay replay <deadLetterJobId>");

    if (!flagBoolean(args.flags, "yes") && !(await confirm(`Replay dead-lettered delivery ${id}?`))) return;

    const result = await client.dlq.retry(id);
    success(`Replay queued for ${id} -- new status: ${result.status}`);
  });
}
