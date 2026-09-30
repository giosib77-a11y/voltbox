"""Argon2 runs beside the event loop, not on it.

What it covers: a sign-in whose hash is running leaves the worker free to answer
another request - with a registered email and with an unknown one, whose dummy
hash must still run so the two take the same time - and a burst of sign-ins
queued for the hash does not hold the connection pool while it waits.
Notes: the hash is held open by replacing the synchronous `verify_password` with
one that blocks until the test lets it go. It runs wherever the real one would:
on the loop, it stalls the loop, which is what the first test detects. The
requests go through the real `get_db`, each on its own connection, so the data
is committed and removed by hand, as in test_orders_concurrency.
"""

import asyncio
import threading
from collections.abc import AsyncGenerator, Callable

import httpx
import pytest
from app.core import security
from app.core.config import settings
from app.db.models import RefreshToken, User
from app.db.session import SessionLocal
from app.main import app
from app.services.auth import _DUMMY_HASH
from httpx import ASGITransport
from sqlalchemy import delete

from tests.factories import make_user

EMAIL = "hashing@voltbox.ge"
PASSWORD = "supersecret1"


class HeldHash:
    """`verify_password`, held open until `release` - or, as a safety, a few seconds."""

    def __init__(self, real: Callable[[str, str], bool]) -> None:
        self.real = real
        self.entered = threading.Event()
        self.finished = threading.Event()
        self.release = threading.Event()
        self.hashes: list[str] = []

    def __call__(self, password: str, password_hash: str) -> bool:
        self.hashes.append(password_hash)
        self.entered.set()
        self.release.wait(timeout=3)
        try:
            return self.real(password, password_hash)
        finally:
            self.finished.set()


@pytest.fixture
def held(monkeypatch: pytest.MonkeyPatch) -> HeldHash:
    fake = HeldHash(security.verify_password)
    monkeypatch.setattr(security, "verify_password", fake)
    return fake


@pytest.fixture
async def account() -> AsyncGenerator[User]:
    async with SessionLocal() as setup:
        user = await make_user(setup, email=EMAIL, password=PASSWORD)
        await setup.commit()

    yield user

    async with SessionLocal() as cleanup:
        await cleanup.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
        await cleanup.execute(delete(User).where(User.id == user.id))
        await cleanup.commit()


@pytest.fixture
async def http() -> AsyncGenerator[httpx.AsyncClient]:
    """The app as deployed: a session of its own per request, from the real pool."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def _until(event: threading.Event) -> None:
    for _ in range(500):
        if event.is_set():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("the hash was never reached")


@pytest.mark.parametrize("email", [EMAIL, "nobody-here@voltbox.ge"], ids=["registered", "unknown"])
async def test_a_sign_in_being_hashed_does_not_hold_up_another_request(
    account: User, held: HeldHash, http: httpx.AsyncClient, email: str
) -> None:
    """The API runs one worker; on the loop, every hash stalled every request."""
    signing_in = asyncio.create_task(
        http.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    )
    await _until(held.entered)

    other = await asyncio.wait_for(http.get("/api/v1/categories"), timeout=5)

    assert not held.finished.is_set(), "the other request waited for the hash to finish"
    assert other.status_code == 200
    held.release.set()
    response = await signing_in
    if email == EMAIL:
        assert response.status_code == 200
    else:
        # The unknown address still pays for a hash, so it answers no sooner.
        assert held.hashes == [_DUMMY_HASH]
        assert response.status_code == 401


async def test_sign_ins_queued_for_the_hash_leave_the_pool_to_others(
    account: User, held: HeldHash, http: httpx.AsyncClient
) -> None:
    """More sign-ins than the pool has connections, all waiting on one hash.

    Hashes run one at a time, so the rest queue. Had each kept the connection
    its lookup used, the pool would be theirs and any request needing the
    database would wait for all of them.
    """
    burst = settings.db_pool_size + settings.db_max_overflow + 1
    signing_in = [
        asyncio.create_task(
            http.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        )
        for _ in range(burst)
    ]
    await _until(held.entered)
    # Let every one of them reach its lookup and queue behind the held hash.
    await asyncio.sleep(0.5)

    try:
        other = await asyncio.wait_for(http.get("/api/v1/categories"), timeout=5)
    except TimeoutError:
        raise AssertionError("the other request found no free connection in the pool") from None
    finally:
        held.release.set()
        responses = await asyncio.gather(*signing_in)

    assert other.status_code == 200
    assert [r.status_code for r in responses] == [200] * burst
