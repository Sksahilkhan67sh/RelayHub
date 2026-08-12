import { ParsedArgs, flagString } from "../args.js";
import { getClient, run } from "../client.js";
import { printJson, color } from "../output.js";

export async function whoamiCommand(args: ParsedArgs): Promise<void> {
  await run(async () => {
    const client = getClient({ apiKey: flagString(args.flags, "api-key"), baseUrl: flagString(args.flags, "base-url") });
    const me = await client.auth.me();

    if (args.flags.json) {
      printJson(me);
      return;
    }
    console.log(`${color.bold(me.user.full_name)} <${me.user.email}>`);
    console.log(`${color.gray("org:")}  ${me.organization.name} (${me.organization.slug})`);
    console.log(`${color.gray("role:")} ${me.role}`);
  });
}
