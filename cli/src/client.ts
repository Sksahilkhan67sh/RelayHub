import { RelayHubClient, RelayHubError } from "relayhub-sdk";
import { resolveApiKey, resolveBaseUrl } from "./config.js";
import { color, error } from "./output.js";

export function getClient(flags: { apiKey?: string; baseUrl?: string }): RelayHubClient {
  const apiKey = resolveApiKey(flags.apiKey);
  if (!apiKey) {
    error("No API key configured. Run " + color.bold("relay login") + " or set RELAYHUB_API_KEY.");
    process.exit(1);
  }
  return new RelayHubClient({ apiKey, baseUrl: resolveBaseUrl(flags.baseUrl) });
}

/** Wraps a command's async body, printing RelayHubError messages cleanly instead of a raw stack trace. */
export async function run(fn: () => Promise<void>): Promise<void> {
  try {
    await fn();
  } catch (err) {
    if (err instanceof RelayHubError) {
      error(err.message);
      if (err.code) console.error(color.gray(`  code: ${err.code}`));
      if (err.requestId) console.error(color.gray(`  request id: ${err.requestId}`));
    } else {
      error(err instanceof Error ? err.message : String(err));
    }
    process.exit(1);
  }
}
