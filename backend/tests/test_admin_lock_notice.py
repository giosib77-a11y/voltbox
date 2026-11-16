"""The Telegram message when failed passwords lock an administrator out (A-037).

What it covers: one message per lock - on the guess that sets it, through any of
the three doors that count a wrong password (sign-in, change-password, the email
change) - with the address masked and nothing about who was guessing; none for a
customer's lock, none when Telegram is off, and no way for Telegram's own
failure, or its slowness, to change the answer the guesser gets.
Notes: the sender runs against an httpx.MockTransport, as test_telegram.py's
does. Nothing here reaches the network: conftest blanks the token, and the
fixture below sets a fake one only for the test.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Generator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.core.config import settings
from app.db.models import ROLE_ADMIN, User
from app.main import app
from app.services import outbound, telegram
from pydantic import SecretStr
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_user, respond_while_held

TOKEN = "7412345678:AAH-sEcReTtOkEn_0123456789abcdefghij"
SECRET_PART = "sEcReTtOkEn_0123456789abcdefghij"
CHAT_ID = "-1001234567890"

LOGIN = "/api/v1/auth/login"
CHANGE = "/api/v1/auth/change-password"
ME = "/api/v1/auth/me"
ADMIN_EMAIL = "boss@example.ge"
MASKED = "b***@example.ge"
RIGHT = "supersecret1"
WRONG = "definitely-not-it"

Handler = Callable[[httpx.Request], Awaitable[httpx.Response]]


class FakeTelegram:
    """sendMessage, recording what it was sent and answering what the test says."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.answer: Handler = self.ok

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return await self.answer(request)

    @staticmethod
    async def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    def texts(self) -> list[str]:
        return [json.loads(request.content)["text"] for request in self.requests]


@pytest.fixture
def fake_telegram(monkeypatch: pytest.MonkeyPatch) -> FakeTelegram:
    """The transport is always the fake; whether it is switched ON is the test's."""
    fake = FakeTelegram()
    monkeypatch.setattr(telegram, "_transport", httpx.MockTransport(fake.handle))
    monkeypatch.setattr(outbound, "RETRY_DELAYS", (0.0, 0.0))
    return fake


@pytest.fixture
def telegram_on(fake_telegram: FakeTelegram, monkeypatch: pytest.MonkeyPatch) -> FakeTelegram:
    monkeypatch.setattr(settings, "telegram_bot_token", SecretStr(TOKEN))
    monkeypatch.setattr(settings, "telegram_chat_id", CHAT_ID)
    return fake_telegram


@pytest.fixture
def captured_logs() -> Generator[list[logging.LogRecord]]:
    """Every record, from the root logger - not caplog, for the reason
    test_unhandled_errors.py gives."""
    records: list[logging.LogRecord] = []

    class Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Collector(level=logging.DEBUG)
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)


async def _guess(client: httpx.AsyncClient, email: str = ADMIN_EMAIL) -> httpx.Response:
    return await client.post(LOGIN, json={"email": email, "password": WRONG})


async def _guesses(client: httpx.AsyncClient, times: int, email: str = ADMIN_EMAIL) -> None:
    for _ in range(times):
        await _guess(client, email)


async def _admin(db: AsyncSession) -> User:
    return await make_user(db, email=ADMIN_EMAIL, role=ROLE_ADMIN, password=RIGHT)


# ── sign-in ──────────────────────────────────────────────────────────────────


async def test_the_guess_that_locks_an_admin_sends_one_message(
    client: httpx.AsyncClient, db: AsyncSession, telegram_on: FakeTelegram
) -> None:
    await _admin(db)

    await _guesses(client, settings.max_failed_logins - 1)
    assert telegram_on.requests == []  # a lock that has not happened is not announced

    last = await _guess(client)
    # The answer to the guess that locked is the answer to any other wrong one.
    assert last.status_code == 401
    assert last.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert len(telegram_on.requests) == 1

    # Refused from here on, the right password included: nothing more is sent.
    await _guesses(client, 3)
    right = await client.post(LOGIN, json={"email": ADMIN_EMAIL, "password": RIGHT})
    assert right.json()["error"]["code"] == "TOO_MANY_LOGIN_ATTEMPTS"
    assert len(telegram_on.requests) == 1


async def test_the_message_names_the_account_masked_and_nothing_about_the_guesser(
    client: httpx.AsyncClient, db: AsyncSession, telegram_on: FakeTelegram
) -> None:
    await _admin(db)

    # A client the message could be tempted to describe.
    await _guesses(client, settings.max_failed_logins)

    (request,) = telegram_on.requests
    body = json.loads(request.content)
    text = body["text"]
    assert body["chat_id"] == CHAT_ID
    assert request.url.path == f"/bot{TOKEN}/sendMessage"
    assert MASKED in text
    assert ADMIN_EMAIL not in text
    assert "boss" not in text
    assert "127.0.0.1" not in text  # the address ASGITransport reports for its client
    assert "python-httpx" not in text  # nor its user agent
    assert "IP" not in text
    # The time the lock ends, in the shop's timezone, not an interval.
    assert ":" in text.splitlines()[-1]


async def test_a_customers_lock_tells_nobody(
    client: httpx.AsyncClient, db: AsyncSession, telegram_on: FakeTelegram
) -> None:
    await make_user(db, email="buyer@example.ge", password=RIGHT)

    await _guesses(client, settings.max_failed_logins + 2, email="buyer@example.ge")

    # It did lock - the refusal is the proof - and it sent nothing.
    refused = await client.post(LOGIN, json={"email": "buyer@example.ge", "password": RIGHT})
    assert refused.json()["error"]["code"] == "TOO_MANY_LOGIN_ATTEMPTS"
    assert telegram_on.requests == []


async def test_nothing_is_sent_when_telegram_is_off_and_the_answer_is_the_same(
    client: httpx.AsyncClient, db: AsyncSession, fake_telegram: FakeTelegram
) -> None:
    """The fake transport is installed but the token and chat are blank, as in a
    test run and in a deployment that never set them."""
    assert not settings.telegram_enabled
    await _admin(db)

    await _guesses(client, settings.max_failed_logins - 1)
    last = await _guess(client)

    assert last.status_code == 401
    assert last.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert fake_telegram.requests == []


async def test_half_configured_telegram_sends_nothing(
    client: httpx.AsyncClient,
    db: AsyncSession,
    fake_telegram: FakeTelegram,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "telegram_bot_token", SecretStr(TOKEN))  # no chat id
    await _admin(db)

    await _guesses(client, settings.max_failed_logins)

    assert fake_telegram.requests == []


async def test_each_lock_is_announced_once_even_when_the_account_is_locked_again(
    client: httpx.AsyncClient, db: AsyncSession, telegram_on: FakeTelegram
) -> None:
    admin = await _admin(db)
    await _guesses(client, settings.max_failed_logins)
    assert len(telegram_on.requests) == 1

    # The lock runs out; the next run of wrong passwords is a new lock.
    await db.execute(
        update(User)
        .where(User.id == admin.id)
        .values(locked_until=datetime.now(UTC) - timedelta(seconds=1))
        .execution_options(synchronize_session="fetch")
    )
    await db.commit()
    await _guesses(client, settings.max_failed_logins - 1)
    assert len(telegram_on.requests) == 1
    await _guess(client)

    assert len(telegram_on.requests) == 2


async def test_locking_one_admin_does_not_announce_another(
    client: httpx.AsyncClient, db: AsyncSession, telegram_on: FakeTelegram
) -> None:
    await _admin(db)
    await make_user(db, email="second@example.ge", role=ROLE_ADMIN)

    await _guesses(client, settings.max_failed_logins)

    assert len(telegram_on.requests) == 1
    assert "second" not in telegram_on.texts()[0]


# ── Telegram cannot change the answer, and the answer does not wait for it ───


async def _refuse_with_status(request: httpx.Request) -> httpx.Response:
    return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})


async def _unavailable(request: httpx.Request) -> httpx.Response:
    return httpx.Response(502, json={"ok": False, "description": "Bad Gateway"})


async def _unreachable(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError(f"cannot reach {request.url}", request=request)


async def _explodes(request: httpx.Request) -> httpx.Response:
    raise RuntimeError(f"unexpected failure for {request.url}")


@pytest.mark.parametrize("answer", [_refuse_with_status, _unavailable, _unreachable, _explodes])
async def test_a_failed_send_changes_nothing_for_the_guesser_and_logs_no_secret(
    client: httpx.AsyncClient,
    db: AsyncSession,
    telegram_on: FakeTelegram,
    captured_logs: list[logging.LogRecord],
    answer: Handler,
) -> None:
    telegram_on.answer = answer
    await _admin(db)

    await _guesses(client, settings.max_failed_logins - 1)
    last = await _guess(client)

    assert last.status_code == 401
    assert last.json()["error"]["code"] == "INVALID_CREDENTIALS"
    errors = [r for r in captured_logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert "administrator account lock was not sent" in errors[0].getMessage()
    # Not the token, in whatever form httpx or the exception put it - and not
    # the account either: the line says that a message was lost, not whose.
    everything = "\n".join(f"{r.name} {r.getMessage()}" for r in captured_logs)
    assert SECRET_PART not in everything
    assert "boss" not in everything
    # And the lock is real: the failure to tell the owner did not undo it.
    refused = await client.post(LOGIN, json={"email": ADMIN_EMAIL, "password": RIGHT})
    assert refused.json()["error"]["code"] == "TOO_MANY_LOGIN_ATTEMPTS"


async def test_the_response_goes_out_before_telegram_answers(
    client: httpx.AsyncClient, db: AsyncSession, telegram_on: FakeTelegram
) -> None:
    release = asyncio.Event()

    async def held(request: httpx.Request) -> httpx.Response:
        await release.wait()
        return await FakeTelegram.ok(request)

    telegram_on.answer = held
    await _admin(db)
    await _guesses(client, settings.max_failed_logins - 1)

    status, still_sending = await respond_while_held(
        app, LOGIN, {"email": ADMIN_EMAIL, "password": WRONG}, release
    )

    assert status == 401
    assert still_sending  # the send was still waiting on Telegram
    assert len(telegram_on.requests) == 1


# ── the other two doors that count a wrong password ──────────────────────────


async def _wrong_current_password(
    client: httpx.AsyncClient, user: User, door: str
) -> httpx.Response:
    if door == "change-password":
        return await client.post(
            CHANGE,
            headers=auth_header(user),
            json={"currentPassword": WRONG, "newPassword": "k7#Rm2!pQzWx"},
        )
    return await client.patch(
        ME,
        headers=auth_header(user),
        json={"email": "thief@example.ge", "currentPassword": WRONG},
    )


@pytest.mark.parametrize("door", ["change-password", "email-change"])
async def test_a_lock_set_by_a_wrong_current_password_is_announced_once(
    client: httpx.AsyncClient, db: AsyncSession, telegram_on: FakeTelegram, door: str
) -> None:
    admin = await _admin(db)

    for _ in range(settings.max_failed_logins - 1):
        await _wrong_current_password(client, admin, door)
    assert telegram_on.requests == []

    last = await _wrong_current_password(client, admin, door)
    assert last.status_code == 400
    assert last.json()["error"]["code"] == "INVALID_CURRENT_PASSWORD"
    assert len(telegram_on.texts()) == 1
    assert MASKED in telegram_on.texts()[0]

    # Locked now: the next guess is refused as locked and says nothing more.
    again = await _wrong_current_password(client, admin, door)
    assert again.status_code == 429
    assert len(telegram_on.requests) == 1


async def test_guesses_through_two_doors_add_up_to_one_lock_and_one_message(
    client: httpx.AsyncClient, db: AsyncSession, telegram_on: FakeTelegram
) -> None:
    admin = await _admin(db)
    half = settings.max_failed_logins // 2

    for _ in range(half):
        await _wrong_current_password(client, admin, "change-password")
    await _guesses(client, settings.max_failed_logins - half)

    assert len(telegram_on.requests) == 1


async def test_a_customers_wrong_current_passwords_tell_nobody(
    client: httpx.AsyncClient, db: AsyncSession, telegram_on: FakeTelegram
) -> None:
    buyer = await make_user(db, email="buyer@example.ge", password=RIGHT)

    for _ in range(settings.max_failed_logins):
        await _wrong_current_password(client, buyer, "change-password")

    again = await _wrong_current_password(client, buyer, "change-password")
    assert again.status_code == 429  # locked
    assert telegram_on.requests == []


# ── the message itself ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("email", "masked"),
    [
        ("boss@example.ge", "b***@example.ge"),
        ("nino.kapanadze@mail.example.com", "n***@mail.example.com"),
        # One letter would be the whole local part: shown as nothing.
        ("a@example.ge", "***@example.ge"),
        ("Ab@x.ge", "A***@x.ge"),
    ],
)
def test_the_address_is_masked(email: str, masked: str) -> None:
    assert telegram.mask_email(email) == masked


def test_the_time_is_the_shops_not_utc() -> None:
    notice = telegram.AdminLockNotice(
        email=ADMIN_EMAIL, locked_until=datetime(2026, 11, 16, 8, 30, tzinfo=UTC)
    )

    text = telegram.admin_lock_text(notice)

    assert "12:30" in text  # Asia/Tbilisi is UTC+4
    assert "08:30" not in text
    assert MASKED in text
