import { warn, info, color } from "../output.js";

/**
 * RelayHub has no "Projects" concept -- endpoints and events belong directly to
 * your organization (see sdks/node/README.md and docs/api for the same note).
 * This command exists (so `relay projects` isn't a broken/missing command) but
 * says so honestly instead of faking a project list against an API that doesn't
 * have one.
 */
export async function projectsCommand(): Promise<void> {
  warn("RelayHub doesn't have a \"Projects\" concept.");
  info("Endpoints and events belong directly to your organization.");
  console.log(color.gray("Try `relay whoami` to see your current organization, or `relay endpoints list`."));
}
