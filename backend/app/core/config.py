from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "RelayHub"
    ENV: str = Field(default="development")  # development | staging | production
    DEBUG: bool = False
    API_V1_PREFIX: str = "/v1"

    # Security
    SECRET_KEY: str = Field(..., description="Used for JWT signing; must be set via env")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JWT_ALGORITHM: str = "HS256"
    PASSWORD_HASH_SCHEME: str = "bcrypt"

    # Password reset / invitation tokens (see auth/password_reset_service.py,
    # auth/invitation_service.py). Short-lived and one-time-use by design.
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    INVITATION_TOKEN_EXPIRE_DAYS: int = 7

    # Used to build links embedded in transactional emails (reset link, invite link),
    # and where GitHub OAuth login redirects back to once tokens are issued.
    FRONTEND_URL: str = "http://localhost:3000"

    # GitHub OAuth login (see auth/github_oauth.py). Disabled -- the "Continue with
    # GitHub" button/endpoints return a clear error -- whenever CLIENT_ID is empty,
    # so this is safe to leave unset in any environment that doesn't need it.
    # Create the OAuth App at https://github.com/settings/developers ; its
    # "Authorization callback URL" must exactly match GITHUB_OAUTH_REDIRECT_URI.
    GITHUB_OAUTH_CLIENT_ID: str = ""
    GITHUB_OAUTH_CLIENT_SECRET: str = ""
    GITHUB_OAUTH_REDIRECT_URI: str = "http://localhost:8000/v1/auth/github/callback"

    # Database
    DATABASE_URL: str = Field(..., description="postgresql+asyncpg://user:pass@host:5432/db")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Rate limiting defaults (overridden per-plan at runtime)
    DEFAULT_RATE_LIMIT_PER_MIN: int = 100

    # Encryption (envelope encryption master key for secrets-at-rest)
    ENCRYPTION_MASTER_KEY: str = Field(..., description="Base64 32-byte key for Fernet/AES envelope encryption")

    # Outbound delivery / SSRF protection
    BLOCK_PRIVATE_IP_TARGETS: bool = True
    ALLOW_HTTP_ENDPOINTS_IN_DEV: bool = True

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Notifications -- email delivery via Resend's HTTP API (https://resend.com),
    # not SMTP. This started as SMTP but that broke in production: Render (and
    # many other PaaS free tiers) block outbound SMTP ports at the network level,
    # so smtplib's raw socket connect failed with "OSError: [Errno 101] Network
    # is unreachable" regardless of how correct the SMTP credentials were. An
    # HTTPS API call has no such problem. Leave RESEND_API_KEY empty to disable
    # email sending entirely -- see notification_client.py's _send_email, which
    # raises a clear NotificationDeliveryError rather than silently dropping mail.
    RESEND_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "RelayHub <alerts@relayhub.dev>"

    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    LOG_LEVEL: str = "INFO"

    # Insights / AI Intelligence Layer (Phase 3). All deterministic thresholds --
    # nothing here talks to an AI provider, see AI_PROVIDER settings below for that.
    INSIGHTS_MIN_SAMPLE_SIZE: int = 20  # below this, health/anomaly checks report UNKNOWN rather than guess
    INSIGHTS_HEALTH_WINDOW_MINUTES: int = 60
    INSIGHTS_BASELINE_LOOKBACK_WINDOWS: int = 6  # compare current window vs the preceding N windows
    INSIGHTS_ANOMALY_MIN_RATE_DELTA: float = 0.15  # 15 percentage points minimum movement to flag a rate anomaly
    INSIGHTS_ANOMALY_MIN_LATENCY_DELTA_RATIO: float = 0.5  # p95 latency must move by >=50% vs baseline
    INSIGHTS_INCIDENT_STABILITY_WINDOWS: int = 2  # consecutive healthy windows required before RESOLVED

    # AI provider abstraction (Phase 3, section 8; extended by the Universal AI
    # Provider & Model Compatibility phase -- see backend/app/modules/ai_gateway/
    # and docs/ai/providers.md). Disabled by default -- the deterministic
    # pipeline (health/anomaly/incident/RCA) works fully without it.
    #
    # AI_PROVIDER selects the PRIMARY provider and is unchanged in meaning from
    # before this phase: existing deployments with AI_PROVIDER=anthropic plus
    # AI_PROVIDER_API_KEY/AI_PROVIDER_MODEL keep working with zero config
    # changes (backward compatibility, see PHASE_UNIVERSAL_AI_AUDIT.md section 7).
    AI_PROVIDER_ENABLED: bool = False
    AI_PROVIDER: str = "anthropic"  # anthropic | openai | gemini | xai
    AI_PROVIDER_API_KEY: str = ""
    AI_PROVIDER_MODEL: str = "claude-sonnet-4-6"
    AI_PROVIDER_TIMEOUT_SECONDS: int = 20
    AI_PROVIDER_MAX_TOKENS: int = 1000

    # Optional automatic fallback provider (Step 19). Empty string (default) =
    # no fallback; a primary-provider failure fails safe exactly as it always
    # has. Only used for transient failures (timeout/rate-limit/unavailable),
    # never for auth or invalid-request errors -- see ai_gateway/gateway.py.
    AI_FALLBACK_PROVIDER: str = ""

    # Per-provider credentials/model, used when that provider is AI_PROVIDER or
    # AI_FALLBACK_PROVIDER and the generic AI_PROVIDER_API_KEY above isn't the
    # one meant for it (e.g. AI_PROVIDER=openai, AI_FALLBACK_PROVIDER=anthropic
    # needs both sets of credentials configured).
    AI_OPENAI_API_KEY: str = ""
    AI_OPENAI_MODEL: str = "gpt-4o"
    AI_GEMINI_API_KEY: str = ""
    AI_GEMINI_MODEL: str = "gemini-1.5-pro"
    AI_XAI_API_KEY: str = ""
    AI_XAI_MODEL: str = "grok-2-latest"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
