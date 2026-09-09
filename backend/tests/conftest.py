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
os.environ.setdefault("APP_ENV", "test")
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://voltbox:voltbox@localhost:55432/voltbox_test"
)

import httpx
from alembic import command
from alembic.config import Config
from app.db.session import engine, get_db
from app.main import app
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _run_alembic(direction: str) -> None:
    """Alembic სინქრონულია და env.py-ში `asyncio.run`-ს იძახებს, ამიტომ ცალკე
    ნაკადში უნდა გაეშვას — მიმდინარე event loop-ში ჩალაგება შეუძლებელია."""
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
