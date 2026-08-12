const isColorEnabled = !process.env.NO_COLOR && process.stdout.isTTY;

function wrap(code: string): (text: string) => string {
  return (text: string) => (isColorEnabled ? `\x1b[${code}m${text}\x1b[0m` : text);
}

export const color = {
  red: wrap("31"),
  green: wrap("32"),
  yellow: wrap("33"),
  blue: wrap("34"),
  magenta: wrap("35"),
  cyan: wrap("36"),
  gray: wrap("90"),
  bold: wrap("1"),
};

export function success(message: string): void {
  console.log(`${color.green("✓")} ${message}`);
}

export function error(message: string): void {
  console.error(`${color.red("✗")} ${message}`);
}

export function warn(message: string): void {
  console.error(`${color.yellow("!")} ${message}`);
}

export function info(message: string): void {
  console.log(`${color.cyan("i")} ${message}`);
}

/** Simple fixed-width table -- no dependency, good enough for terminal-width CLI output. */
export function printTable(columns: string[], rows: string[][]): void {
  if (rows.length === 0) {
    console.log(color.gray("(no results)"));
    return;
  }
  const widths = columns.map((col, i) => Math.max(col.length, ...rows.map((r) => (r[i] ?? "").length)));
  const renderRow = (cells: string[]) => cells.map((c, i) => c.padEnd(widths[i] ?? 0)).join("  ");

  console.log(color.bold(renderRow(columns)));
  console.log(color.gray(widths.map((w) => "-".repeat(w)).join("  ")));
  for (const row of rows) console.log(renderRow(row));
}

export function printJson(data: unknown): void {
  console.log(JSON.stringify(data, null, 2));
}

/** Prompts y/N on stdin for destructive commands. Returns true only on an explicit "y"/"yes". */
export async function confirm(message: string): Promise<boolean> {
  const readline = await import("node:readline/promises");
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    const answer = await rl.question(`${color.yellow("?")} ${message} ${color.gray("[y/N]")} `);
    return ["y", "yes"].includes(answer.trim().toLowerCase());
  } finally {
    rl.close();
  }
}
