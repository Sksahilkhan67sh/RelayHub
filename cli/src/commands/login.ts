import { RelayHubClient } from "relayhub-sdk";
import { hostname } from "node:os";
import { ParsedArgs, flagString } from "../args.js";
import { saveConfig, loadConfig, resolveBaseUrl } from "../config.js";
import { success, info, color } from "../output.js";
import { run } from "../client.js";

async function prompt(question: string): Promise<string> {
  const readline = await import("node:readline/promises");
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    return await rl.question(question);
  } finally {
    rl.close();
  }
}

export async function loginCommand(args: ParsedArgs): Promise<void> {
  await run(async () => {
    const baseUrl = resolveBaseUrl(flagString(args.flags, "base-url"));
    const directApiKey = flagString(args.flags, "api-key");

    if (directApiKey) {
      saveConfig({ ...loadConfig(), apiKey: directApiKey, baseUrl });
      success("API key saved.");
      return;
    }

    info("Interactive login -- this creates a dedicated CLI API key, not a stored password.");
    const email = await prompt("Email: ");
    const password = await prompt("Password: ");

    // auth.login() doesn't require an API key itself -- the "unused" value here
    // never leaves this call (login/register are the only unauthenticated routes
    // this client is used for).
    const authClient = new RelayHubClient({ apiKey: "unused", baseUrl });
    const tokens = await authClient.auth.login({ email, password });

    const sessionClient = new RelayHubClient({ apiKey: tokens.access_token, baseUrl });
    const created = await sessionClient.apiKeys.create({ name: `CLI - ${hostname()}` });

    saveConfig({ apiKey: created.key, baseUrl, email });
    success(`Logged in as ${email}. Created API key "${created.name}" (${created.key_prefix}...) for the CLI.`);
    console.log(color.gray(`Config saved to ~/.relayhub/config.json`));
  });
}
