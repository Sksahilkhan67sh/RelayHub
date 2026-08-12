import { ParsedArgs, flagString, flagBoolean } from "../args.js";
import { getClient, run } from "../client.js";
import { printTable, printJson, success, error, confirm } from "../output.js";

export async function endpointsCommand(args: ParsedArgs): Promise<void> {
  await run(async () => {
    const client = getClient({ apiKey: flagString(args.flags, "api-key"), baseUrl: flagString(args.flags, "base-url") });
    const action = args.positionals[0] ?? "list";

    switch (action) {
      case "list": {
        const endpoints = await client.endpoints.list();
        if (args.flags.json) return printJson(endpoints);
        printTable(
          ["ID", "NAME", "URL", "ENV", "HEALTH"],
          endpoints.map((e) => [e.id, e.name, e.url, e.environment, e.health_status])
        );
        return;
      }
      case "get": {
        const id = args.positionals[1];
        if (!id) return error("Usage: relay endpoints get <id>");
        printJson(await client.endpoints.get(id));
        return;
      }
      case "create": {
        const name = flagString(args.flags, "name");
        const url = flagString(args.flags, "url");
        if (!name || !url) return error("Usage: relay endpoints create --name <name> --url <url> [--environment test|live]");
        const created = await client.endpoints.create({ name, url, environment: flagString(args.flags, "environment") as "test" | "live" | undefined });
        success(`Created endpoint ${created.id}`);
        printJson(created);
        return;
      }
      case "update": {
        const id = args.positionals[1];
        if (!id) return error("Usage: relay endpoints update <id> [--name ...] [--url ...]");
        const updated = await client.endpoints.update(id, {
          name: flagString(args.flags, "name"),
          url: flagString(args.flags, "url"),
        });
        success(`Updated endpoint ${id}`);
        printJson(updated);
        return;
      }
      case "delete": {
        const id = args.positionals[1];
        if (!id) return error("Usage: relay endpoints delete <id>");
        if (!flagBoolean(args.flags, "yes") && !(await confirm(`Delete endpoint ${id}?`))) return;
        await client.endpoints.delete(id);
        success(`Deleted endpoint ${id}`);
        return;
      }
      case "rotate-secret": {
        const id = args.positionals[1];
        if (!id) return error("Usage: relay endpoints rotate-secret <id>");
        if (!flagBoolean(args.flags, "yes") && !(await confirm(`Rotate the signing secret for endpoint ${id}?`))) return;
        const secret = await client.endpoints.rotateSecret(id);
        success("Secret rotated. Store it now -- it will not be shown again.");
        printJson(secret);
        return;
      }
      default:
        error(`Unknown subcommand: endpoints ${action}`);
        console.log("Usage: relay endpoints <list|get|create|update|delete|rotate-secret> [args]");
    }
  });
}
