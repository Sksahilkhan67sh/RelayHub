# relay -- the official RelayHub CLI

Command-line interface for [RelayHub](https://relayhub.dev), built on top of
[`@relayhub/sdk`](../sdks/node) -- the CLI has no HTTP logic of its own; every
command is a thin wrapper that formats the SDK's typed responses for a terminal.

## Install

```bash
npm install -g @relayhub/cli
```

For local development against the SDK in this repo:

```bash
cd sdks/node && npm install && npm run build
cd ../../cli && npm install && npm run build
node dist/index.js --help
```

## Authenticate

```bash
relay login                          # interactive: email + password, creates a dedicated CLI API key
relay login --api-key rh_live_...    # non-interactive: use an existing key
```

`login` doesn't store your password -- it authenticates once, then creates a new
API key (named `CLI - <hostname>`) via `POST /v1/api-keys` and stores *that*.
Config lives at `~/.relayhub/config.json` (mode `0600`).

Resolution order for the API key on every command: `--api-key` flag →
`RELAYHUB_API_KEY` env var → config file.

## Commands

```
relay login                  Authenticate interactively, or with --api-key
relay logout                 Remove the stored API key
relay whoami                 Show the current user, organization, and role
relay projects                (RelayHub has no Projects concept -- explains why, see below)
relay endpoints                list | get | create | update | delete | rotate-secret
relay publish <event.type>   Publish an event
relay deliveries              list | get   -- searches the delivery log
relay replay <jobId>          Replay a dead-lettered delivery
relay dlq                      list | get | retry | discard | export
relay analytics                summary | top-endpoints | health
relay billing                  plans | subscription | usage | invoices | portal
relay notifications            list | create | test | delete | history  (alert rules)
relay config                   get | set | path
relay version                Print the CLI version
relay doctor                  Diagnose your setup (config, auth, connectivity)
relay completion <bash|zsh>   Print a shell completion script
```

Global flags on every command: `--api-key`, `--base-url`, `--json` (raw JSON
instead of a table), `--yes` (skip confirmation on destructive commands).

### `relay projects`

RelayHub doesn't have a "Projects" entity -- endpoints and events belong
directly to an organization. This command exists (so it isn't a missing/broken
command) but says so plainly instead of faking a project list against an API
that has no such resource. See the same note in
[`sdks/node/README.md`](../sdks/node/README.md).

### `relay replay` / `relay dlq retry`

Both call the same real endpoint: `POST /v1/dlq/{id}/retry`. "Replay" isn't a
separate feature in the API -- it's what retrying a dead-lettered delivery is
called in the product. `relay replay <id>` is a shorter alias for
`relay dlq retry <id>`.

### `relay notifications`

Maps to RelayHub's alert-rule endpoints (`/v1/alerts/*`) -- there's no separate
`/notifications` route in the backend.

## Examples

```bash
relay endpoints create --name "Prod webhook" --url https://api.example.com/hook --environment live
relay publish payment.success --payload '{"order_id":"ord_123","amount":4200}'
relay deliveries list --status failed,retrying --limit 10
relay dlq list --endpoint-id ep_abc123
relay replay dlj_xyz789 --yes
relay analytics summary --start-date 2026-07-01 --end-date 2026-08-01
```

## Shell completion

```bash
relay completion bash >> ~/.bashrc
relay completion zsh  >> ~/.zshrc
```

## Development

```bash
npm install
npm run typecheck
npm run build
node dist/index.js doctor
```

## License

MIT
