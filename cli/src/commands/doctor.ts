import { ParsedArgs, flagString } from "../args.js";
import { resolveApiKey, resolveBaseUrl, CONFIG_FILE_PATH } from "../config.js";
import { RelayHubClient, RelayHubError } from "relayhub-sdk";
import { success, error, warn, color } from "../output.js";
import { existsSync } from "node:fs";

export async function doctorCommand(args: ParsedArgs): Promise<void> {
  console.log(color.bold("RelayHub CLI diagnostics"));
  console.log("");

  const nodeMajor = Number(process.version.slice(1).split(".")[0]);
  if (nodeMajor >= 18) {
    success(`Node.js ${process.version} (>= 18 required)`);
  } else {
    error(`Node.js ${process.version} -- the CLI requires Node 18+`);
  }

  if (existsSync(CONFIG_FILE_PATH)) {
    success(`Config file found at ${CONFIG_FILE_PATH}`);
  } else {
    warn(`No config file at ${CONFIG_FILE_PATH} -- run \`relay login\` or set RELAYHUB_API_KEY`);
  }

  const apiKey = resolveApiKey(flagString(args.flags, "api-key"));
  const baseUrl = resolveBaseUrl(flagString(args.flags, "base-url"));

  if (!apiKey) {
    error("No API key resolved (checked --api-key, RELAYHUB_API_KEY, and config file).");
    console.log("");
    console.log(color.gray("Run `relay login` to fix this."));
    process.exitCode = 1;
    return;
  }
  success(`API key resolved (${apiKey.slice(0, 8)}...)`);
  success(`Base URL: ${baseUrl ?? "(default) https://api.relayhub.dev/v1"}`);

  try {
    const client = new RelayHubClient({ apiKey, baseUrl, timeoutMs: 10_000, maxRetries: 0 });
    const me = await client.auth.me();
    success(`Connected -- authenticated as ${me.user.email} (${me.organization.name})`);
  } catch (err) {
    if (err instanceof RelayHubError) {
      error(`Could not authenticate: ${err.message} (status ${err.status})`);
    } else {
      error(`Could not reach the API: ${err instanceof Error ? err.message : String(err)}`);
    }
    console.log("");
    console.log(color.gray("Check your API key and network connection, or run `relay login` again."));
    process.exitCode = 1;
    return;
  }

  console.log("");
  success("Everything looks good.");
}
