#!/usr/bin/env node
import { parseArgs } from "./args.js";
import { color } from "./output.js";
import { loginCommand } from "./commands/login.js";
import { logoutCommand } from "./commands/logout.js";
import { whoamiCommand } from "./commands/whoami.js";
import { projectsCommand } from "./commands/projects.js";
import { endpointsCommand } from "./commands/endpoints.js";
import { publishCommand } from "./commands/publish.js";
import { deliveriesCommand } from "./commands/deliveries.js";
import { replayCommand } from "./commands/replay.js";
import { dlqCommand } from "./commands/dlq.js";
import { analyticsCommand } from "./commands/analytics.js";
import { insightsCommand } from "./commands/insights.js";
import { billingCommand } from "./commands/billing.js";
import { notificationsCommand } from "./commands/notifications.js";
import { configCommand } from "./commands/config.js";
import { versionCommand } from "./commands/version.js";
import { doctorCommand } from "./commands/doctor.js";
import { completionScript, COMMAND_NAMES } from "./completions.js";

const HELP = `${color.bold("relay")} -- the official RelayHub CLI

${color.bold("Usage:")}
  relay <command> [subcommand] [args] [flags]

${color.bold("Commands:")}
  login                  Authenticate interactively, or with --api-key
  logout                 Remove the stored API key
  whoami                 Show the current user, organization, and role
  projects               (RelayHub has no Projects concept -- explains why)
  endpoints               list | get | create | update | delete | rotate-secret
  publish <event.type>   Publish an event
  deliveries              list | get   -- searches the delivery log
  replay <jobId>          Replay a dead-lettered delivery
  dlq                      list | get | retry | discard | export
  analytics                summary | top-endpoints | health
  insights                  health | health-history | anomalies | incidents | incident | rca | recommendations | timeline
  billing                  plans | subscription | usage | invoices | portal
  notifications            list | create | test | delete | history  (alert rules)
  config                   get | set | path
  version                Print the CLI version
  doctor                  Diagnose your setup (config, auth, connectivity)
  completion <bash|zsh>   Print a shell completion script

${color.bold("Global flags:")}
  --api-key <key>        Override the resolved API key for this command
  --base-url <url>       Override the API base URL for this command
  --json                 Print raw JSON instead of a formatted table
  --yes                  Skip confirmation prompts on destructive commands

${color.gray("Docs: docs/api -- Examples: examples/")}
`;

async function main(): Promise<void> {
  const [command, ...rest] = process.argv.slice(2);
  const args = parseArgs(rest);

  switch (command) {
    case undefined:
    case "help":
    case "--help":
    case "-h":
      console.log(HELP);
      return;
    case "login":
      return loginCommand(args);
    case "logout":
      return logoutCommand();
    case "whoami":
      return whoamiCommand(args);
    case "projects":
      return projectsCommand();
    case "endpoints":
      return endpointsCommand(args);
    case "publish":
      return publishCommand(args);
    case "deliveries":
      return deliveriesCommand(args);
    case "replay":
      return replayCommand(args);
    case "dlq":
      return dlqCommand(args);
    case "analytics":
      return analyticsCommand(args);
    case "insights":
      return insightsCommand(args);
    case "billing":
      return billingCommand(args);
    case "notifications":
      return notificationsCommand(args);
    case "config":
      return configCommand(args);
    case "version":
    case "--version":
    case "-v":
      return versionCommand();
    case "doctor":
      return doctorCommand(args);
    case "completion": {
      const shell = args.positionals[0];
      const script = shell ? completionScript(shell) : null;
      if (!script) {
        console.error(`Usage: relay completion <bash|zsh>`);
        process.exit(1);
      }
      console.log(script);
      return;
    }
    default:
      console.error(`Unknown command: ${command}`);
      console.error(`Known commands: ${COMMAND_NAMES.join(", ")}`);
      console.error(`Run \`relay help\` for usage.`);
      process.exit(1);
  }
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
