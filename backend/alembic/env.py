"""Alembic-ის გარემო.

URL Settings-იდან მოდის (და არა alembic.ini-დან), რომ საიდუმლო ერთ ადგილას იყოს.
მიგრაციები async ძრავზე გადის `run_sync`-ით, რადგან Alembic თავად სინქრონულია.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from app.core.config import settings

# ყველა მოდელი უნდა დაიმპორტდეს, თორემ autogenerate ცხრილებს ვერ დაინახავს
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.ssl import build_connect_args
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
        connect_args=build_connect_args(),
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
