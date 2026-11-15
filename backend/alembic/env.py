"""Alembic-ის გარემო.

URL Settings-იდან მოდის (და არა alembic.ini-დან), რომ საიდუმლო ერთ ადგილას იყოს.
მიგრაციები async ძრავზე გადის `run_sync`-ით, რადგან Alembic თავად სინქრონულია.
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from alembic.util import CommandError
from app.core.config import settings

# ყველა მოდელი უნდა დაიმპორტდეს, თორემ autogenerate ცხრილებს ვერ დაინახავს
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.local_url import migration_refusal
from app.db.ssl import build_connect_args
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

config = context.config
if config.config_file_name is not None:
    # disable_existing_loggers=False, or this call switches off every logger
    # that is not named in alembic.ini - which is all of the application's own.
    # The test suite runs migrations at session start, so voltbox.access and
    # voltbox.error were dead for the whole run and nothing could assert on a
    # log line. The same would happen to any process that ran a migration
    # before serving.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Config values go through ConfigParser interpolation, where a bare `%` (the
# percent-encoding of a password, `%40` for `@`) is a syntax error whose message
# quotes the whole value - password included - in the traceback. Doubling it here
# is undone by get_main_option / get_section, so the A-061 guard below and the
# engine still see the URL exactly as configured. Offline mode does not read this
# option back; it uses `settings` directly.
config.set_main_option(
    "sqlalchemy.url", settings.database_url.get_secret_value().replace("%", "%%")
)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url.get_secret_value(),
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
    # Every online command (upgrade, downgrade, stamp, check, current) passes
    # here, before any engine exists. On 2026-11-12 a test run reached live
    # Supabase and ran `downgrade base` there; the target is now checked, not
    # assumed. VOLTBOX_ALLOW_REMOTE_MIGRATION=1 overrides this and nothing else;
    # offline `--sql` never gets here and is unchanged.
    refusal = migration_refusal(config.get_main_option("sqlalchemy.url") or "", os.environ)
    if refusal is not None:
        raise CommandError(refusal)

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
