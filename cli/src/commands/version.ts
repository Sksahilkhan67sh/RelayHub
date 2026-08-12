import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

export function versionCommand(): void {
  try {
    const pkg = JSON.parse(readFileSync(join(__dirname, "..", "..", "package.json"), "utf-8"));
    console.log(`relay ${pkg.version}`);
    console.log(`node ${process.version}`);
  } catch {
    console.log("relay (version unknown -- package.json not found relative to build output)");
  }
}
