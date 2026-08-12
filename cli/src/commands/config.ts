import { ParsedArgs } from "../args.js";
import { loadConfig, saveConfig, CONFIG_FILE_PATH } from "../config.js";
import { printJson, success, error, color } from "../output.js";

export async function configCommand(args: ParsedArgs): Promise<void> {
  const action = args.positionals[0] ?? "get";

  switch (action) {
    case "get": {
      const config = loadConfig();
      const redacted = { ...config, apiKey: config.apiKey ? config.apiKey.slice(0, 10) + "..." : undefined };
      printJson(redacted);
      console.log(color.gray(`(${CONFIG_FILE_PATH})`));
      return;
    }
    case "set": {
      const key = args.positionals[1];
      const value = args.positionals[2];
      if (!key || value === undefined) return error("Usage: relay config set <baseUrl|email> <value>");
      if (key !== "baseUrl" && key !== "email") return error(`Unsupported config key: ${key}. Use "relay login --api-key" to set the API key.`);
      saveConfig({ ...loadConfig(), [key]: value });
      success(`Set ${key}`);
      return;
    }
    case "path": {
      console.log(CONFIG_FILE_PATH);
      return;
    }
    default:
      console.log("Usage: relay config <get|set|path>");
  }
}
