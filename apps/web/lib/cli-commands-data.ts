export interface Command {
  name: string;
  usage: string;
  note?: string;
}

export const COMMANDS: Command[] = [
  { name: "login", usage: "relay login [--api-key <key>] [--base-url <url>]", note: "Interactive by default: prompts for email/password, then creates a dedicated CLI-only API key and stores that -- never your password, never a raw session token." },
  { name: "logout", usage: "relay logout", note: "Removes the stored API key from ~/.relayhub/config.json." },
  { name: "whoami", usage: "relay whoami [--json]", note: "Shows your name, email, organization, and role." },
  { name: "projects", usage: "relay projects", note: "RelayHub has no \"Projects\" concept -- this command exists just to say so clearly instead of erroring, and points you to `endpoints list` instead." },
  { name: "endpoints", usage: "relay endpoints <list|get|create|update|delete|rotate-secret> [args]" },
  { name: "publish", usage: "relay publish <event.type> [--payload '<json>'] [--environment test|live] [--idempotency-key <key>]" },
  { name: "deliveries", usage: "relay deliveries get <jobId>" },
  { name: "replay", usage: "relay replay <deadLetterJobId>" },
  { name: "dlq", usage: "relay dlq <list|get|retry|discard|export> [args]" },
  { name: "analytics", usage: "relay analytics <summary|top-endpoints|health> [--environment ...] [--start-date ...] [--end-date ...]" },
  { name: "billing", usage: "relay billing <plans|subscription|usage|invoices|portal>" },
  { name: "notifications", usage: "relay notifications <list|create|test|delete|history> [args]", note: "Manages alert rules -- \"notifications\" is this CLI's name for the backend's alerts module." },
  { name: "config", usage: "relay config <get|set|path>", note: "get prints your config with the API key redacted to its first 10 characters." },
  { name: "doctor", usage: "relay doctor", note: "Checks Node version, config file presence, API key resolution, and live connectivity in one command." },
  { name: "completion", usage: "relay completion <bash|zsh>", note: "Prints a shell completion script." },
  { name: "version", usage: "relay version", note: "Prints the CLI version and your Node.js version." },
];

export const GLOBAL_FLAGS = [
  { flag: "--api-key <key>", note: "Override the resolved API key for this command" },
  { flag: "--base-url <url>", note: "Override the API base URL for this command" },
  { flag: "--json", note: "Print raw JSON instead of a formatted table" },
  { flag: "--yes", note: "Skip confirmation prompts on destructive commands" },
];
