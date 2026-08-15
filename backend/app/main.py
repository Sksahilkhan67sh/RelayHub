from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.error_handlers import register_error_handlers
from app.core.health import check_database, check_redis
from app.middleware.body_size_limit import BodySizeLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.modules.admin.routes import router as admin_router
from app.modules.alerts.routes import router as alerts_router
from app.modules.analytics.routes import router as analytics_router
from app.modules.api_keys.routes import router as api_keys_router
from app.modules.audit.routes import router as audit_router
from app.modules.content.routes import admin_router as content_admin_router, public_router as content_public_router
from app.modules.auth.invitation_routes import router as invitations_router
from app.modules.auth.org_routes import router as org_router
from app.modules.auth.routes import router as auth_router
from app.modules.billing.routes import router as billing_router
from app.modules.delivery.routes import router as deliveries_router
from app.modules.dlq.routes import router as dlq_router
from app.modules.endpoints.routes import router as endpoints_router
from app.modules.events.routes import router as events_router
from app.modules.logs.routes import router as logs_router

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
app.include_router(analytics_router, prefix=settings.API_V1_PREFIX)
app.include_router(alerts_router, prefix=settings.API_V1_PREFIX)
app.include_router(billing_router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_router, prefix=settings.API_V1_PREFIX)
app.include_router(content_admin_router, prefix=settings.API_V1_PREFIX)
app.include_router(content_public_router, prefix=settings.API_V1_PREFIX)


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
