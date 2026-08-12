import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export interface CliConfig {
  apiKey?: string;
  baseUrl?: string;
  /** Set by `relay login`; informational only -- the API key is what actually authenticates. */
  email?: string;
}

const CONFIG_DIR = join(homedir(), ".relayhub");
const CONFIG_PATH = join(CONFIG_DIR, "config.json");

export function loadConfig(): CliConfig {
  if (!existsSync(CONFIG_PATH)) return {};
  try {
    return JSON.parse(readFileSync(CONFIG_PATH, "utf-8")) as CliConfig;
  } catch {
    return {};
  }
}

export function saveConfig(config: CliConfig): void {
  if (!existsSync(CONFIG_DIR)) mkdirSync(CONFIG_DIR, { recursive: true, mode: 0o700 });
  writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), { mode: 0o600 });
}

export function clearConfig(): void {
  saveConfig({});
}

export const CONFIG_FILE_PATH = CONFIG_PATH;

/** Resolution order: --api-key flag > RELAYHUB_API_KEY env var > config file. */
export function resolveApiKey(flagValue: string | undefined): string | undefined {
  return flagValue || process.env.RELAYHUB_API_KEY || loadConfig().apiKey;
}

export function resolveBaseUrl(flagValue: string | undefined): string | undefined {
  return flagValue || process.env.RELAYHUB_BASE_URL || loadConfig().baseUrl;
}
