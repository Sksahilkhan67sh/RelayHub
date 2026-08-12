import { existsSync } from "node:fs";
import { CONFIG_FILE_PATH, clearConfig } from "../config.js";
import { success, info } from "../output.js";
import { run } from "../client.js";

export async function logoutCommand(): Promise<void> {
  await run(async () => {
    if (!existsSync(CONFIG_FILE_PATH)) {
      info("Already logged out (no config file found).");
      return;
    }
    clearConfig();
    success("Logged out. Removed stored API key from ~/.relayhub/config.json");
  });
}
