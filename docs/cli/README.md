# RelayHub CLI Reference

Package: [`cli/`](../../cli). Full usage guide with more examples:
[`cli/README.md`](../../cli/README.md). This page documents every command that
actually exists in `cli/src/index.ts` -- nothing here is planned or aspirational.

Every command accepts the global flags `--api-key`, `--base-url`, `--json`, and
`--yes` (skips confirmation on destructive commands). Authentication resolves in
order: `--api-key` flag → `RELAYHUB_API_KEY` env var → `~/.relayhub/config.json`.

## `relay login`

- **Purpose:** authenticate the CLI.
- **Syntax:** `relay login` (interactive) or `relay login --api-key <key>` (non-interactive)
- **Auth required:** none to run it -- it's how you get authenticated.
- **Behavior:** interactive mode prompts for email/password, logs in via
  `POST /auth/login`, then creates a dedicated API key via `POST /api-keys`
  (named `CLI - <hostname>`) and stores *that* key -- your password is never
  written to disk.

## `relay logout`

- **Purpose:** remove the stored API key.
- **Syntax:** `relay logout`
- **Auth required:** none.
- **Behavior:** deletes `~/.relayhub/config.json`'s contents.

## `relay whoami`

- **Purpose:** show the current user, organization, and role.
- **Syntax:** `relay whoami [--json]`
- **Auth required:** yes (session-derived API key).
- **Calls:** `GET /auth/me`

## `relay projects`

- **Purpose:** exists so `relay projects` isn't a missing/broken command.
- **Syntax:** `relay projects`
- **Auth required:** none.
- **Behavior:** RelayHub has no Projects resource -- this command explains that
  plainly instead of faking a project list. See `docs/api/README.md` for why.

## `relay endpoints`

- **Purpose:** manage endpoints.
- **Syntax:** `relay endpoints <list|get|create|update|delete|rotate-secret> [args] [flags]`
- **Auth required:** yes; `create`/`update`/`delete`/`rotate-secret` require an `admin`-scoped session.
- **Examples:**
  ```bash
  relay endpoints list
  relay endpoints create --name "Prod" --url https://api.example.com/hook --environment live
  relay endpoints delete ep_abc123 --yes
  relay endpoints rotate-secret ep_abc123 --yes
  ```
- **Destructive commands** (`delete`, `rotate-secret`) prompt for confirmation unless `--yes` is passed.

## `relay publish <event.type>`

- **Purpose:** publish an event.
- **Syntax:** `relay publish <event.type> [--payload '<json>'] [--environment test|live] [--idempotency-key <key>]`
- **Auth required:** an API key with the `events:write` scope.
- **Calls:** `POST /events`
- **Example:** `relay publish payment.success --payload '{"order_id":"ord_123"}' --idempotency-key ord_123-payment-success`

## `relay deliveries`

- **Purpose:** search the delivery log, or fetch one delivery job.
- **Syntax:** `relay deliveries [list] [--endpoint-id ...] [--status a,b] [--event-type ...] [--environment ...] [--limit N] [--offset N]` or `relay deliveries get <jobId>`
- **Auth required:** yes.
- **Calls:** `GET /logs` (list) or `GET /deliveries/{id}` (get)

## `relay replay <jobId>`

- **Purpose:** replay a dead-lettered delivery. A shorter alias for `relay dlq retry`.
- **Syntax:** `relay replay <jobId> [--yes]`
- **Auth required:** `admin`-scoped session.
- **Calls:** `POST /dlq/{id}/retry`
- **Confirms** before running unless `--yes` is passed.

## `relay dlq`

- **Purpose:** manage the dead-letter queue.
- **Syntax:** `relay dlq <list|get|retry|discard|export> [args] [flags]`
- **Auth required:** yes; `retry`/`discard` require `admin`.
- **Examples:**
  ```bash
  relay dlq list --endpoint-id ep_abc123
  relay dlq retry dlj_xyz789 --yes
  relay dlq discard dlj_xyz789 --yes   # permanent -- confirms unless --yes
  relay dlq export > dlq.csv
  ```

## `relay analytics`

- **Purpose:** view delivery analytics.
- **Syntax:** `relay analytics <summary|top-endpoints|health> [--environment ...] [--start-date ...] [--end-date ...]`
- **Auth required:** yes.
- **Calls:** `GET /analytics/summary`, `/top-endpoints`, or `/endpoint-health`

## `relay billing`

- **Purpose:** view/manage billing.
- **Syntax:** `relay billing <plans|subscription|usage|invoices|portal>`
- **Auth required:** yes; `plans` needs no auth (public endpoint) but the command still resolves a client the same way. `portal` opens a Stripe-hosted URL -- requires the `owner` role server-side.
- **Calls:** `GET /billing/plans|subscription|usage|invoices`, `POST /billing/portal`

## `relay notifications`

- **Purpose:** manage alert rules (RelayHub's actual notification mechanism -- no separate `/notifications` API exists).
- **Syntax:** `relay notifications <list|create|test|delete|history> [args] [flags]`
- **Auth required:** yes; `create`/`delete` require `admin`.
- **Example:**
  ```bash
  relay notifications create --condition endpoint_down --channel slack --channel-config '{"webhook_url":"https://hooks.slack.com/..."}' --severity critical
  relay notifications test rule_abc123
  ```

## `relay config`

- **Purpose:** inspect/edit the local CLI config file.
- **Syntax:** `relay config <get|set|path>`
- **Auth required:** none.
- **Note:** `relay config set` only supports `baseUrl` and `email` -- the API key
  is set via `relay login`, not `config set`, since it needs to be created
  through the API, not typed in freely.

## `relay version`

- **Purpose:** print the CLI version and Node.js runtime version.
- **Syntax:** `relay version`
- **Auth required:** none.

## `relay doctor`

- **Purpose:** diagnose your local setup: Node version, config file presence,
  resolved API key, and a live connectivity check against `GET /auth/me`.
- **Syntax:** `relay doctor`
- **Auth required:** none to run it; reports whether auth actually works.
- **Exit code:** non-zero if any check fails.

## `relay completion <bash|zsh>`

- **Purpose:** print a shell completion script.
- **Syntax:** `relay completion bash` or `relay completion zsh`
- **Auth required:** none.
- **Install:** `relay completion bash >> ~/.bashrc` (or `zsh` / `~/.zshrc`)
