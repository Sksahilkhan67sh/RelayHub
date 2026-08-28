from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.error_handlers import register_error_handlers
from app.core.health import check_database, check_redis
from app.core.metrics import refresh_reliability_gauges
from app.core.tracing import setup_tracing
from app.db.session import get_db
from app.middleware.body_size_limit import BodySizeLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.modules.admin.routes import router as admin_router
from app.modules.alerts.routes import router as alerts_router
from app.modules.analytics.routes import router as analytics_router
from app.modules.api_keys.routes import router as api_keys_router
from app.modules.audit.routes import router as audit_router
from app.modules.auth.invitation_routes import router as invitations_router
from app.modules.auth.org_routes import router as org_router
from app.modules.auth.routes import router as auth_router
from app.modules.billing.routes import router as billing_router
from app.modules.content.routes import admin_router as content_admin_router
from app.modules.content.routes import public_router as content_public_router
from app.modules.delivery.routes import router as deliveries_router
from app.modules.dlq.routes import router as dlq_router
from app.modules.endpoints.routes import router as endpoints_router
from app.modules.events.routes import router as events_router
from app.modules.insights.copilot.routes import router as insights_copilot_router
from app.modules.insights.routes import router as insights_intelligence_router
from app.modules.logs.routes import router as logs_router
from app.modules.newsletter.routes import router as newsletter_router
from app.modules.notifications.routes import router as notifications_router

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs" if settings.ENV != "production" else None,
    redoc_url=None,
)

# Order matters: Starlette applies middleware in reverse of add order, so the last
# one added here runs first on the way in / last on the way out. Body-size rejection
# should happen before anything else touches the request; security headers should
# decorate every response, including error responses from the handlers below.
app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)

register_error_handlers(app)

# Metrics export (Phase 2 follow-up -- see app/core/metrics.py's module docstring
# for the full design rationale). `instrument()` attaches middleware that
# accumulates HTTP request count/latency/in-progress into the default
# prometheus_client registry as the app serves real traffic; deliberately no
# `.expose()` call here, since the custom `/metrics` route below needs to refresh
# the reliability gauges (which share that same default registry) immediately
# before rendering, and `.expose()` doesn't offer a hook for that.
Instrumentator().instrument(app)

# Distributed tracing (OTel follow-up -- see app/core/tracing.py's module
# docstring). No-op with zero overhead when OTEL_EXPORTER_OTLP_ENDPOINT is unset
# (the default everywhere that hasn't explicitly configured a collector, including
# the test suite): setup_tracing returns None and FastAPIInstrumentor is never
# called, so this app behaves exactly as it did before tracing existed.
if setup_tracing("relayhub-api") is not None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, excluded_urls="/health/live,/health/ready,/metrics")

app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(org_router, prefix=settings.API_V1_PREFIX)
app.include_router(invitations_router, prefix=settings.API_V1_PREFIX)
app.include_router(audit_router, prefix=settings.API_V1_PREFIX)
app.include_router(api_keys_router, prefix=settings.API_V1_PREFIX)
app.include_router(endpoints_router, prefix=settings.API_V1_PREFIX)
app.include_router(events_router, prefix=settings.API_V1_PREFIX)
app.include_router(deliveries_router, prefix=settings.API_V1_PREFIX)
app.include_router(dlq_router, prefix=settings.API_V1_PREFIX)
app.include_router(logs_router, prefix=settings.API_V1_PREFIX)
# Mounted twice deliberately -- see app/modules/analytics/routes.py's module
# docstring: /v1/analytics is the original, published, SDK-referenced path (kept
# unchanged for backward compatibility); /v1/insights is an identical alias the
# first-party web dashboard uses instead, to avoid ad-blocker filter lists that
# match the substring "analytics" in first-party request URLs.
app.include_router(analytics_router, prefix=f"{settings.API_V1_PREFIX}/analytics")
app.include_router(analytics_router, prefix=f"{settings.API_V1_PREFIX}/insights", include_in_schema=False)
# Phase 3 AI intelligence layer -- mounted at /v1/insights/intelligence/..., NOT
# bare /v1/insights/..., to avoid colliding with the analytics alias mounted
# immediately above (see insights/routes.py's module docstring for why).
app.include_router(insights_intelligence_router, prefix=settings.API_V1_PREFIX)
# Phase 5B -- conversational copilot, mounted under the same intelligence prefix
# (see insights/copilot/routes.py's module docstring).
app.include_router(insights_copilot_router, prefix=settings.API_V1_PREFIX)
app.include_router(alerts_router, prefix=settings.API_V1_PREFIX)
app.include_router(notifications_router, prefix=settings.API_V1_PREFIX)
app.include_router(billing_router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_router, prefix=settings.API_V1_PREFIX)
app.include_router(content_admin_router, prefix=settings.API_V1_PREFIX)
app.include_router(content_public_router, prefix=settings.API_V1_PREFIX)
app.include_router(newsletter_router, prefix=settings.API_V1_PREFIX)


@app.get("/health/live", tags=["health"])
async def health_live():
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def health_ready():
    db_status, redis_status = await check_database(), await check_redis()
    dependencies = {d.name: {"ok": d.ok, "detail": d.detail} for d in (db_status, redis_status)}
    if db_status.ok and redis_status.ok:
        return {"status": "ready", "dependencies": dependencies}
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "dependencies": dependencies},
    )


@app.get("/metrics", include_in_schema=False, tags=["health"])
async def metrics(db: AsyncSession = Depends(get_db)):
    """
    Prometheus text-exposition endpoint. Combines HTTP-level metrics (accumulated
    passively by the Instrumentator middleware above) with reliability gauges
    refreshed from a live DB query on every scrape -- see app/core/metrics.py for
    why those are gauges-refreshed-per-scrape rather than in-process counters.

    Deliberately unauthenticated, matching standard Prometheus scrape conventions
    (most scrapers can't do interactive auth) -- this endpoint must be
    network-restricted at the deployment/ingress level, not exposed publicly. It
    reveals aggregate operational counts (queue depth, worker health, latency), not
    tenant data -- no event payloads, endpoint URLs, or other customer content ever
    appear here.
    """
    await refresh_reliability_gauges(db)
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
