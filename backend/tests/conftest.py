import os
import uuid

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ENCRYPTION_MASTER_KEY", "2jTG0yvUfKASUN5PNtSlYVG5mR_-uXOqbVg63m70fIU=")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db

# Import all ORM models here so Base.metadata is fully populated before create_all().
# As new modules (api_keys, endpoints, events, ...) add models, import them here too.
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.api_keys import models as _api_keys_models  # noqa: F401
from app.modules.audit import models as _audit_models  # noqa: F401
from app.modules.endpoints import models as _endpoints_models  # noqa: F401
from app.modules.events import models as _events_models  # noqa: F401
from app.modules.delivery import models as _delivery_models  # noqa: F401
from app.modules.alerts import models as _alerts_models  # noqa: F401
from app.modules.billing import models as _billing_models  # noqa: F401
from app.modules.admin import models as _admin_models  # noqa: F401
from app.modules.content import models as _content_models  # noqa: F401
from app.modules.insights import models as _insights_models  # noqa: F401


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    from app.common.notification_client import InMemoryNotificationDispatcher, get_notification_dispatcher
    from app.common.queue_client import get_queue_client, InMemoryQueueClient
    from app.common.rate_limiter import get_rate_limiter, InMemoryRateLimiter
    from app.common.stripe_client import FakeStripeClient, get_stripe_client
    from app.main import app

    async def _override_get_db():
        yield db_session

    fake_queue = InMemoryQueueClient()
    fake_rate_limiter = InMemoryRateLimiter()
    fake_stripe = FakeStripeClient()
    fake_notifications = InMemoryNotificationDispatcher()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_queue_client] = lambda: fake_queue
    app.dependency_overrides[get_rate_limiter] = lambda: fake_rate_limiter
    app.dependency_overrides[get_stripe_client] = lambda: fake_stripe
    app.dependency_overrides[get_notification_dispatcher] = lambda: fake_notifications
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.fake_queue = fake_queue  # type: ignore[attr-defined]
        ac.fake_rate_limiter = fake_rate_limiter  # type: ignore[attr-defined]
        ac.fake_stripe = fake_stripe  # type: ignore[attr-defined]
        ac.fake_notifications = fake_notifications  # type: ignore[attr-defined]
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def unique_email():
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


async def register_and_get_token(client, email: str) -> str:
    resp = await client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPass1",
            "full_name": "Sahil Khan",
            "organization_name": "AlignCraft",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def create_api_key(client, token: str, *, environment: str = "test", scopes: list[str] | None = None) -> str:
    resp = await client.post(
        "/v1/api-keys",
        json={"name": "test key", "environment": environment, "scopes": scopes or ["events:write", "events:read"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["key"]


async def create_endpoint(
    client, token: str, *, url: str = "https://example.com/hook", environment: str = "test", subscribed_event_types: list[str] | None = None
) -> str:
    resp = await client.post(
        "/v1/endpoints",
        json={
            "name": "test endpoint",
            "url": url,
            "environment": environment,
            "subscribed_event_types": subscribed_event_types or [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def upgrade_to_pro(client, db_session, token: str) -> None:
    """
    The Free plan (default for every new org, Phase 3l) allows only 1 endpoint.
    Tests that legitimately need multiple endpoints under one org call this first.
    """
    from app.modules.billing import service as billing_service

    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = uuid.UUID(me_resp.json()["organization"]["id"])
    subscription = await billing_service.get_or_create_subscription(db_session, organization_id=org_id)
    pro_plan = await billing_service.get_or_create_plan(db_session, "pro")
    subscription.plan_id = pro_plan.id
    await db_session.commit()
    await billing_service.sync_organization_plan_fields(db_session, organization_id=org_id, plan=pro_plan)


async def make_platform_admin(client, db_session, token: str) -> None:
    from sqlalchemy import select

    from app.modules.auth.models import User

    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = uuid.UUID(me_resp.json()["user"]["id"])
    user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one()
    user.is_platform_admin = True
    await db_session.commit()
