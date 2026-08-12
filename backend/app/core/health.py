from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine


@dataclass
class DependencyStatus:
    name: str
    ok: bool
    detail: str | None = None


async def check_database() -> DependencyStatus:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return DependencyStatus(name="database", ok=True)
    except Exception as exc:  # noqa: BLE001 - readiness probe must never raise
        return DependencyStatus(name="database", ok=False, detail=str(exc.__class__.__name__))


async def check_redis() -> DependencyStatus:
    import redis.asyncio as redis

    client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
    try:
        await client.ping()
        return DependencyStatus(name="redis", ok=True)
    except Exception as exc:  # noqa: BLE001 - readiness probe must never raise
        return DependencyStatus(name="redis", ok=False, detail=str(exc.__class__.__name__))
    finally:
        await client.aclose()
