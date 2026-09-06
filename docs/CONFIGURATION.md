# Configuration Reference

Every environment variable the backend reads is a field on the single
`Settings` class in `backend/app/core/config.py` — this document mirrors it
exactly. If you add a setting, add it here and to `backend/.env.example` in
the same change (see `CONTRIBUTING.md`). No real secret values appear below.

Two fields have no default and are **required** — the app raises a validation
error at startup without them: `SECRET_KEY`, `DATABASE_URL`, and
`ENCRYPTION_MASTER_KEY`. Everything else has a safe default.

## App

| Name | Purpose | Required | Dev default | Production importance |
|---|---|---|---|---|
| `APP_NAME` | Display name used in a few places (emails, docs) | No | `RelayHub` | Cosmetic |
| `ENV` | `development` \| `staging` \| `production` | No | `development` | **High.** Gates three real behaviors: `/docs` (Swagger UI) is only disabled when this is exactly `production`; plain-HTTP (non-TLS) endpoint URLs are only rejected when this is `production` (see `ALLOW_HTTP_ENDPOINTS_IN_DEV` below); the HSTS security header is only sent when this is `production`. **Must be `production` in any real deployment** — leaving it at the default has real security consequences, not just cosmetic ones. |
| `DEBUG` | Enables SQLAlchemy SQL echo logging | No | `False` | Low — verbose logs only, not a security concern either way |
| `API_V1_PREFIX` | Path prefix for all versioned routes | No | `/v1` | Changing this is a breaking API change for every SDK/frontend call |

## Security

| Name | Purpose | Required | Dev default | Production importance |
|---|---|---|---|---|
| `SECRET_KEY` | JWT signing key | **Yes** | — | **Critical.** Anyone with this can forge valid access tokens. Rotate = every existing session invalidated. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Dashboard access token lifetime | No | `15` | Shorter = more secure, more refresh traffic |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime (with reuse/family revocation) | No | `30` | — |
| `JWT_ALGORITHM` | JWT signing algorithm | No | `HS256` | Changing requires re-issuing every token |
| `PASSWORD_HASH_SCHEME` | Password hashing scheme | No | `bcrypt` | — |
| `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | Reset-link validity window | No | `30` | — |
| `INVITATION_TOKEN_EXPIRE_DAYS` | Invite-link validity window | No | `7` | — |

## Frontend / OAuth

| Name | Purpose | Required | Dev default | Production importance |
|---|---|---|---|---|
| `FRONTEND_URL` | Base URL used to build links in transactional emails and where GitHub OAuth redirects with tokens after login | No | `http://localhost:3000` | **Must be the real deployed frontend URL in production** — wrong value breaks invite/reset links and OAuth login silently |
| `GITHUB_OAUTH_CLIENT_ID` | GitHub OAuth App client ID | No | empty (feature disabled cleanly) | Leave empty to fully disable "Continue with GitHub" |
| `GITHUB_OAUTH_CLIENT_SECRET` | GitHub OAuth App client secret | No | empty | Same as above |
| `GITHUB_OAUTH_REDIRECT_URI` | Must exactly match the OAuth App's configured callback URL on GitHub | No | `http://localhost:8000/v1/auth/github/callback` | Mismatch = GitHub rejects the callback |

## Database

| Name | Purpose | Required | Dev default | Production importance |
|---|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/db` | **Yes** | — | **Critical** — the entire app is unusable without it |
| `DATABASE_POOL_SIZE` | SQLAlchemy connection pool size | No | `20` | Tune against your Postgres plan's max connections |
| `DATABASE_MAX_OVERFLOW` | Extra connections allowed beyond pool size under load | No | `10` | — |

## Redis / Celery

| Name | Purpose | Required | Dev default | Production importance |
|---|---|---|---|---|
| `REDIS_URL` | Rate-limiter's sliding-window counters | No | `redis://localhost:6379/0` | Required for real deployments — rate limiting silently no-ops without a reachable Redis in some paths, don't rely on that |
| `CELERY_BROKER_URL` | Celery task broker (separate Redis DB index by convention) | No | `redis://localhost:6379/1` | **Critical** — no deliveries/retries happen without a working broker |
| `CELERY_RESULT_BACKEND` | Celery result backend | No | `redis://localhost:6379/2` | — |

## CORS

| Name | Purpose | Required | Dev default | Production importance |
|---|---|---|---|---|
| `CORS_ORIGINS` | JSON array of allowed browser origins | No | `["http://localhost:3000"]` | **Must be the real deployed frontend origin(s) in production** — combined with `allow_credentials=True`, so this must never be `"*"`. A real production incident this session: left at the dev default, the deployed frontend is silently blocked by the browser's CORS check on every API call. |

## Rate limiting

| Name | Purpose | Required | Dev default | Production importance |
|---|---|---|---|---|
| `DEFAULT_RATE_LIMIT_PER_MIN` | Fallback rate limit; overridden per-plan at runtime by `billing/` | No | `100` | — |

## Encryption

| Name | Purpose | Required | Dev default | Production importance |
|---|---|---|---|---|
| `ENCRYPTION_MASTER_KEY` | Base64 32-byte key for Fernet/AES envelope encryption of endpoint signing secrets at rest | **Yes** | — | **Critical.** Losing this makes every stored endpoint secret unrecoverable. Rotating it requires re-encrypting existing rows — not currently automated. |

## Outbound delivery / SSRF protection

| Name | Purpose | Required | Dev default | Production importance |
|---|---|---|---|---|
| `BLOCK_PRIVATE_IP_TARGETS` | Rejects endpoint URLs resolving to a private IP range | No | `True` | **Leave `True` in production** — this is a real SSRF defense, not a convenience toggle |
| `ALLOW_HTTP_ENDPOINTS_IN_DEV` | Allows plain-HTTP (non-TLS) endpoint URLs, combined with `ENV != "production"` | No | `True` | Only actually permissive when `ENV` is not `production` — see the `ENV` entry above |

## Stripe

| Name | Purpose | Required | Dev default | Production importance |
|---|---|---|---|---|
| `STRIPE_SECRET_KEY` | Stripe API secret key | No | empty | Required for billing checkout/portal to function |
| `STRIPE_WEBHOOK_SECRET` | Verifies Stripe webhook signatures | No | empty | Required for `POST /v1/billing/webhook` to accept real events |

## Email (Resend HTTP API)

| Name | Purpose | Required | Dev default | Production importance |
|---|---|---|---|---|
| `RESEND_API_KEY` | Resend API key for transactional email (invites, password reset, alert emails) | No | empty (sending fails with a clear error, doesn't silently no-op) | **Required for real invites/resets to arrive.** Was SMTP originally — switched because Render (and most PaaS free tiers) block outbound SMTP ports at the network level. |
| `EMAIL_FROM_ADDRESS` | The `From:` address/name, e.g. `RelayHub <alerts@yourdomain.com>` | No | `RelayHub <alerts@relayhub.dev>` | Resend requires the sending domain to be verified in your Resend account, or use their shared `onboarding@resend.dev` sender (which can only deliver to your own Resend account's email — real production use needs a verified domain) |

## Observability

| Name | Purpose | Required | Dev default | Production importance |
|---|---|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Real OpenTelemetry OTLP exporter endpoint | No | empty (tracing fully skipped, zero overhead) | Set this to enable real distributed tracing — the code (`core/tracing.py`) is genuine, not a placeholder |
| `LOG_LEVEL` | Application log level | No | `INFO` | — |

`GET /metrics` (Prometheus format) has no on/off setting — it's always served.

## Insights (deterministic health/anomaly detection — no AI involved)

| Name | Purpose | Required | Dev default |
|---|---|---|---|
| `INSIGHTS_MIN_SAMPLE_SIZE` | Below this many samples, health checks report `UNKNOWN` rather than guess | No | `20` |
| `INSIGHTS_HEALTH_WINDOW_MINUTES` | Rolling window size for health scoring | No | `60` |
| `INSIGHTS_BASELINE_LOOKBACK_WINDOWS` | How many prior windows form the comparison baseline | No | `6` |
| `INSIGHTS_ANOMALY_MIN_RATE_DELTA` | Minimum percentage-point movement to flag a rate anomaly | No | `0.15` |
| `INSIGHTS_ANOMALY_MIN_LATENCY_DELTA_RATIO` | Minimum p95 latency movement ratio to flag an anomaly | No | `0.5` |
| `INSIGHTS_INCIDENT_STABILITY_WINDOWS` | Consecutive healthy windows required before an incident auto-resolves | No | `2` |

## AI provider (Insights RCA + Copilot chat)

All disabled/empty by default — the deterministic insights pipeline above
works fully without any of this configured.

| Name | Purpose | Required | Dev default |
|---|---|---|---|
| `AI_PROVIDER_ENABLED` | Master on/off switch for both AI features | No | `False` |
| `AI_PROVIDER` | Primary provider: `anthropic` \| `openai` \| `gemini` \| `xai` | No | `anthropic` |
| `AI_PROVIDER_API_KEY` | Primary provider's API key (also doubles as Anthropic's key for backward compatibility — see `ai_gateway/gateway.py`'s credential-resolution docstring) | No | empty |
| `AI_PROVIDER_MODEL` | Primary provider's model name | No | `claude-sonnet-4-6` |
| `AI_PROVIDER_TIMEOUT_SECONDS` | Per-call timeout | No | `20` |
| `AI_PROVIDER_MAX_TOKENS` | Max output tokens per call | No | `1000` |
| `AI_FALLBACK_PROVIDER` | Second provider to try on a transient failure (timeout/rate-limit/unavailable only — never on an auth or invalid-request error) | No | empty (no fallback) |
| `AI_OPENAI_API_KEY` / `AI_OPENAI_MODEL` | OpenAI credentials/model, used when OpenAI is primary or fallback and isn't covered by the generic settings above | No | empty / `gpt-4o` |
| `AI_GEMINI_API_KEY` / `AI_GEMINI_MODEL` | Same, for Gemini | No | empty / `gemini-1.5-pro` |
| `AI_XAI_API_KEY` / `AI_XAI_MODEL` | Same, for xAI | No | empty / `grok-2-latest` |

See `docs/ai/providers.md` for provider-specific setup notes and
`docs/WHERE_TO_MAKE_CHANGES.md`'s "add an AI provider" section to add a fifth.

## Frontend (`apps/web/.env.example`)

| Name | Purpose | Required | Dev default |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL the frontend calls for the backend API | No | `http://localhost:8000` |
