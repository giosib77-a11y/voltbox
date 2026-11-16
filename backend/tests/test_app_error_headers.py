"""`AppError.headers`: response headers a refusal carries, and the 429s that use them.

Every 429 this API sends says `Retry-After`. slowapi's limits get it from
`main.rate_limit_handler`; the two refusals raised as an `AppError` (a locked
account asked for its password, and one address asked for too many reset
emails) get it from here. The routes themselves are covered where their other
behaviour is, in test_auth.py and test_password_reset.py.
"""

import time
from collections.abc import AsyncIterator

import httpx
import pytest
from app.core import rate_limit
from app.core.errors import AppError, register_exception_handlers
from app.core.headers import BASE_HEADERS
from app.core.rate_limit import (
    MEMORY_STORAGE,
    build_limiter,
    hit_per_address,
    seconds_until_address_resets,
)
from fastapi import FastAPI
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

ADDRESS = "Nino@Example.ge"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/with-headers")
    async def with_headers() -> None:
        raise AppError("Slow down", code="SLOW_DOWN", status_code=429, headers={"Retry-After": "7"})

    @app.get("/without-headers")
    async def without_headers() -> None:
        raise AppError("Gone", code="GONE", status_code=410)

    @app.get("/clashing-headers")
    async def clashing_headers() -> None:
        raise AppError(
            "Slow down",
            code="SLOW_DOWN",
            status_code=429,
            headers={"Retry-After": "7", "X-Content-Type-Options": "custom"},
        )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as http:
        yield http


class TestTheHandler:
    async def test_a_refusal_with_headers_sends_them_and_the_same_body(
        self, client: httpx.AsyncClient
    ) -> None:
        response = await client.get("/with-headers")

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "7"
        assert response.json() == {
            "error": {"code": "SLOW_DOWN", "message": "Slow down", "details": None}
        }
        # The security headers still arrive around it.
        assert response.headers["X-Content-Type-Options"] == BASE_HEADERS["X-Content-Type-Options"]

    async def test_a_refusal_without_headers_is_unchanged(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/without-headers")

        assert response.status_code == 410
        assert "Retry-After" not in response.headers
        assert response.json()["error"]["code"] == "GONE"
        for header, value in BASE_HEADERS.items():
            assert response.headers[header] == value

    async def test_a_header_the_refusal_sets_is_not_overwritten(
        self, client: httpx.AsyncClient
    ) -> None:
        """`_finish` only fills in the security headers that are missing."""
        response = await client.get("/clashing-headers")

        assert response.headers["Retry-After"] == "7"
        assert response.headers["X-Content-Type-Options"] == "custom"


class TestSecondsUntilAnAddressResets:
    @pytest.fixture(autouse=True)
    def counting(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            rate_limit, "limiter", build_limiter(enabled=True, storage_uri=MEMORY_STORAGE)
        )
        monkeypatch.setattr(
            rate_limit, "_address_fallback", FixedWindowRateLimiter(MemoryStorage())
        )

    def test_it_is_the_rest_of_the_window(self) -> None:
        hit_per_address("3/hour", scope="test", address=ADDRESS)

        seconds = seconds_until_address_resets("3/hour", scope="test", address=ADDRESS)

        assert 3590 <= seconds <= 3600

    def test_the_spelling_of_the_address_does_not_matter(self) -> None:
        hit_per_address("3/hour", scope="test", address=ADDRESS)

        seconds = seconds_until_address_resets(
            "3/hour", scope="test", address=ADDRESS.upper() + " "
        )

        # The hit made in the plain spelling is found: a missed lookup would say 1.
        assert 3590 <= seconds <= 3600

    def test_a_window_that_is_over_still_says_one_second(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hit_per_address("3/hour", scope="test", address=ADDRESS)
        later = time.time() + 7200
        monkeypatch.setattr(time, "time", lambda: later)

        assert seconds_until_address_resets("3/hour", scope="test", address=ADDRESS) == 1

    def test_a_dead_store_answers_from_the_process_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            rate_limit,
            "limiter",
            build_limiter(enabled=True, storage_uri="redis://127.0.0.1:1/0"),
        )
        hit_per_address("3/hour", scope="test", address=ADDRESS)  # counted in the fallback

        seconds = seconds_until_address_resets("3/hour", scope="test", address=ADDRESS)

        assert 3590 <= seconds <= 3600

    def test_a_store_that_cannot_answer_gives_the_whole_window(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(*args: object, **kwargs: object) -> None:
            raise ConnectionError("store went away")

        monkeypatch.setattr(rate_limit.limiter.limiter, "get_window_stats", refuse)
        monkeypatch.setattr(rate_limit._address_fallback, "get_window_stats", refuse)

        assert seconds_until_address_resets("3/hour", scope="test", address=ADDRESS) == 3600
