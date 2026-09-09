"""async ძრავი და სესიის ფაბრიკა.

Supabase-ის Session pooler-თან TLS სავალდებულოა, ლოკალურ კონტეინერთან — არა,
ამიტომ connect_args დინამიურად იწყობა (`settings.requires_ssl`).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.ssl import build_connect_args

engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,  # pooler-მა შეიძლება უმოქმედო კავშირი დახუროს
    connect_args=build_connect_args(),
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # commit-ის შემდეგ ატრიბუტები რომ ხელახლა არ ჩაიტვირთოს
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency — თითო მოთხოვნა ერთი სესია, შეცდომაზე rollback."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
