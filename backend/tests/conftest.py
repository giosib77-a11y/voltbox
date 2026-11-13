"""ტესტების საერთო fixture-ები.

ტესტები ცალკე ბაზაზე (`voltbox_test`) მუშაობენ, რომ dev-მონაცემები არ დაზიანდეს.
თითო ტესტი გარე ტრანზაქციაშია გახვეული და ბოლოს rollback ხდება — ასე ტესტები
ერთმანეთისგან იზოლირებულია და ცხრილების ხელახლა შექმნა არ სჭირდებათ.
"""

import asyncio
import os
from collections.abc import AsyncGenerator
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

import pytest

# Settings-ის იმპორტამდე უნდა დაიწეროს — `lru_cache` ერთხელ იკითხავს
# The suite never reads backend/.env: it holds the live Supabase URL and keys,
# and Settings opens it from the working directory (app/core/config.py).
os.environ["VOLTBOX_NO_DOTENV"] = "1"
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-only-secret-value-that-is-long-enough-32")
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://voltbox:voltbox@localhost:55432/voltbox_test"
)
# Every credential that reaches a service outside this machine, blanked. A
# developer's `.env` holds the live ones, and an environment variable beats the
# file: without this, every checkout in a test run would post to the owner's
# Telegram and email the address in it, and the rate limiter would count in the
# production Redis. Tests that need one set it against a fake transport.
# test_no_outbound.py fails when Settings gains a credential not listed here.
OUTBOUND_CREDENTIALS = (
    "TELEGRAM_BOT_TOKEN",
    "RESEND_API_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "REDIS_URL",
)
for _name in OUTBOUND_CREDENTIALS:
    os.environ[_name] = ""

import httpx
from alembic import command
from alembic.config import Config
from app.core.config import get_settings, settings
from app.db.local_url import describe_database_url, is_local_database_url
from app.db.session import engine, get_db
from app.main import app
from httpx import ASGITransport
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


# The environment switches above only work when this file is the first to import
# `app`. On 2026-11-12 a pytest plugin imported it earlier, Settings read the
# live backend/.env, and the session fixture ran `alembic downgrade base` on
# live Supabase. So the suite also checks what it is about to connect to, and
# refuses by name instead of trusting the order of imports. A failure at import
# raises: pytest reports it as a conftest import failure and stops before any
# test is collected, with no database touched.
class UnsafeTestDatabaseError(RuntimeError):
    """The suite was about to use a database that is not a local `*_test` one."""


def require_test_database(url: str | URL, role: str) -> None:
    """Raise unless `url` is a local database whose name ends in `_test`.

    Names the host and database it refused, never the password or the URL.
    """
    if not is_local_database_url(url):
        raise UnsafeTestDatabaseError(
            f"Refusing to let the test suite use {describe_database_url(url)} as {role}: "
            "it is not a local database (localhost, 127.0.0.1 or ::1, with no host override)."
        )
    name = make_url(url).database or ""
    if not name.endswith("_test"):
        raise UnsafeTestDatabaseError(
            f"Refusing to let the test suite use {describe_database_url(url)} as {role}: "
            "the database name must end in `_test`, because the suite drops every table in it."
        )


def require_settings_built_for_this_run() -> None:
    """Raise unless the cached settings hold the URL this file put in the environment.

    `get_settings()` is cached, so if anything imported `app.core.config` before
    the environment above was set, it keeps whatever it read then - possibly
    backend/.env. Compared by host, port, database and user, because `Settings`
    rewrites the scheme and drops `sslmode`.
    """
    expected = make_url(os.environ["DATABASE_URL"])
    for held in (get_settings().database_url, settings.database_url):
        try:
            actual = make_url(held.get_secret_value())
        except ArgumentError:
            actual = None
        if actual is None or (
            (actual.host, actual.port, actual.database, actual.username)
            != (expected.host, expected.port, expected.database, expected.username)
        ):
            raise UnsafeTestDatabaseError(
                "App settings were built before tests/conftest.py set the test environment "
                "- something imported `app` first (a pytest plugin?). They point at "
                f"{describe_database_url(held.get_secret_value())}, not at the test database "
                f"{describe_database_url(expected)}."
            )


require_settings_built_for_this_run()
require_test_database(engine.url, "the test engine")


def _run_alembic(direction: str) -> None:
    """Alembic სინქრონულია და env.py-ში `asyncio.run`-ს იძახებს, ამიტომ ცალკე
    ნაკადში უნდა გაეშვას — მიმდინარე event loop-ში ჩალაგება შეუძლებელია."""
    # The URL env.py will use is settings.database_url; `downgrade base` below
    # drops every table, so it is checked here, right before the call.
    require_test_database(settings.database_url.get_secret_value(), "the alembic target")
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    if direction == "up":
        command.upgrade(config, "head")
    else:
        command.downgrade(config, "base")


@pytest.fixture(scope="session", autouse=True)
async def _create_schema() -> AsyncGenerator[None]:
    """სქემას რეალური მიგრაციებით ვაწყობთ, არა `create_all`-ით.

    ორი მიზეზი: (1) ექსტენსიები (citext, pg_trgm) და RLS მხოლოდ მიგრაციაშია,
    metadata-ში არა; (2) ასე მიგრაციები ყოველ ტესტ-გაშვებაზე მოწმდება და
    მოდელებთან დაშორება მაშინვე გამოჩნდება.
    """
    await asyncio.to_thread(_run_alembic, "down")
    await asyncio.to_thread(_run_alembic, "up")
    yield
    await asyncio.to_thread(_run_alembic, "down")
    await engine.dispose()


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession]:
    """ტრანზაქციაში გახვეული სესია — ტესტის ბოლოს ყველაფერი უკან ბრუნდება."""
    connection = await engine.connect()
    transaction = await connection.begin()
    # join_transaction_mode="create_savepoint" — ტესტები, რომლებიც IntegrityError-ს
    # ელოდებიან, სესიის ტრანზაქციას ანგრევენ; savepoint-ით გარე ტრანზაქცია ხელუხლებელი
    # რჩება და rollback გაფრთხილების გარეშე გადის
    session = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )()
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncGenerator[httpx.AsyncClient]:
    """HTTP კლიენტი, რომელიც იმავე ტრანზაქციულ სესიას იყენებს, რასაც ტესტი."""

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        yield http_client
    app.dependency_overrides.clear()
