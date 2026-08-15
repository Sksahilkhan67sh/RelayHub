import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.base import Base

# Import all module models so autogenerate can see them.
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.api_keys import models as api_keys_models  # noqa: F401
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.endpoints import models as endpoints_models  # noqa: F401
from app.modules.events import models as events_models  # noqa: F401
from app.modules.delivery import models as delivery_models  # noqa: F401
from app.modules.alerts import models as alerts_models  # noqa: F401
from app.modules.billing import models as billing_models  # noqa: F401
from app.modules.admin import models as admin_models  # noqa: F401
from app.modules.content import models as content_models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
