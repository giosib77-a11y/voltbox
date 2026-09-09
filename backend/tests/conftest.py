"""ტესტების საერთო fixture-ები.

ტესტები ცალკე ბაზაზე (`voltbox_test`) მუშაობენ, რომ dev-მონაცემები არ დაზიანდეს.
თითო ტესტი გარე ტრანზაქციაშია გახვეული და ბოლოს rollback ხდება — ასე ტესტები
ერთმანეთისგან იზოლირებულია და ცხრილების ხელახლა შექმნა არ სჭირდებათ.
"""

import os
from collections.abc import AsyncGenerator

import pytest

# Settings-ის იმპორტამდე უნდა დაიწეროს — `lru_cache` ერთხელ იკითხავს
os.environ.setdefault("APP_ENV", "test")
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://voltbox:voltbox@localhost:55432/voltbox_test"
)

import httpx
from app.db.base import Base
from app.db.session import engine, get_db
from app.main import app
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture(scope="session", autouse=True)
async def _create_schema() -> AsyncGenerator[None]:
    """სქემას ტესტ-სესიის დასაწყისში ვქმნით და ბოლოს ვშლით.

    `create_all` განზრახ — მიგრაციების გაშვება ყოველ სესიაზე ნელია; მიგრაციების
    სისწორეს ცალკე ტესტი ამოწმებს (`test_migrations.py`).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession]:
    """ტრანზაქციაში გახვეული სესია — ტესტის ბოლოს ყველაფერი უკან ბრუნდება."""
    connection = await engine.connect()
    transaction = await connection.begin()
    session = async_sessionmaker(bind=connection, expire_on_commit=False)()
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
