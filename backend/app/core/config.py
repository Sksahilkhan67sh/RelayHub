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

    # Used to build links embedded in transactional emails (reset link, invite link).
    FRONTEND_URL: str = "http://localhost:3000"

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

    # Notifications
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "alerts@relayhub.dev"
    SMTP_USE_TLS: bool = True

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

    # AI provider abstraction (Phase 3, section 8). Disabled by default -- the
    # deterministic pipeline (health/anomaly/incident/RCA) works fully without it.
    AI_PROVIDER_ENABLED: bool = False
    AI_PROVIDER: str = "anthropic"  # anthropic | openai | none
    AI_PROVIDER_API_KEY: str = ""
    AI_PROVIDER_MODEL: str = "claude-sonnet-4-6"
    AI_PROVIDER_TIMEOUT_SECONDS: int = 20
    AI_PROVIDER_MAX_TOKENS: int = 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
