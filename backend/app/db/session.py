from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_engine_kwargs: dict = {"pool_pre_ping": True, "echo": settings.DEBUG}

# SQLite (used for local/dev sqlite+aiosqlite and in-memory test DBs) uses SingletonThreadPool /
# StaticPool and does not accept pool_size/max_overflow. Postgres (production) uses QueuePool
# and benefits from explicit sizing under load.
if settings.DATABASE_URL.startswith("postgresql"):
    _engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
    _engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
