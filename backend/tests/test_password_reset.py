"""A shopper resets a forgotten password through a link sent by email.

The email goes out through the real ResendSender, against an
httpx.MockTransport, as the order confirmation's tests do; the token a test
uses is the one read out of that email, so every test walks the path a
shopper does.

What each group pins, and why it is the thing to pin:
- an unknown address is answered exactly as a known one - status, body,
  headers and the SQL that ran - so neither the response nor its timing says
  who is registered;
- a link works once, for less than an hour, and only the newest one;
- using one ends every session of the account;
- the token and the link reach no log line and no response but the email;
- both rate limits, and the refusal while no email can be sent.
"""

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable, Generator, Iterator
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.core import rate_limit
from app.core.config import settings
from app.core.logging import JsonFormatter
from app.core.rate_limit import MEMORY_STORAGE, build_limiter, limiter
from app.core.security import PASSWORD_RESET_TTL
from app.db.models import PasswordResetToken, User
from app.db.session import engine
from app.main import app
from app.services import mailer, outbound
from pydantic import SecretStr
from sqlalchemy import event, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_user, respond_while_held

API_KEY = "re_SeCrEtKeY_4f2a9c1e8b7d6a5f"
SENDER = "VoltBox <no-reply@voltbox.ge>"
SITE = "https://shop.example"

EMAIL = "nino@example.ge"
PASSWORD = "supersecret1"
NEW_PASSWORD = "brand-new-pass-7"

FORGOT = "/api/v1/auth/forgot-password"
RESET = "/api/v1/auth/reset-password"
LOGIN = "/api/v1/auth/login"

#: The httpOnly cookie the refresh token travels in.
COOKIE = "voltbox_refresh"

Handler = Callable[[httpx.Request], Awaitable[httpx.Response]]


class FakeResend:
    """Resend's POST /emails, answering what the test tells it to."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.answer: Handler = self.ok

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return await self.answer(request)

    @staticmethod
    async def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "49a3999c-0ce1-4ea6-ab68-afcd6dc2e794"})

    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(request.content) for request in self.requests]

    def token(self) -> str:
        """The token in the last email sent, read the way a shopper's click does."""
        return _token_in(self.bodies()[-1]["text"])


def _token_in(text: str) -> str:
    match = re.search(r"#token=([A-Za-z0-9_-]+)", text)
    assert match, "the email carries no link"
    return match.group(1)


def _link_in(text: str) -> str:
    match = re.search(r"\S+#token=\S+", text)
    assert match, "the email carries no link"
    return match.group(0)


class RaisingSender:
    """A send that fails with an exception quoting the whole message."""

    def __init__(self) -> None:
        self.emails: list[mailer.Email] = []

    async def send(self, email: mailer.Email) -> str | None:
        self.emails.append(email)
        raise RuntimeError(f"could not render {email.text}")


@pytest.fixture
def fake_resend(monkeypatch: pytest.MonkeyPatch) -> FakeResend:
    fake = FakeResend()
    monkeypatch.setattr(mailer, "_transport", httpx.MockTransport(fake.handle))
    monkeypatch.setattr(outbound, "RETRY_DELAYS", (0.0, 0.0))
    monkeypatch.setattr(settings, "resend_api_key", SecretStr(API_KEY))
    monkeypatch.setattr(settings, "email_from", SENDER)
    monkeypatch.setattr(settings, "site_url", SITE)
    return fake


@pytest.fixture
def captured_logs() -> Generator[list[logging.LogRecord]]:
    """Every record at every level, from the root logger - not caplog, for the
    reason test_unhandled_errors.py gives."""
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


@pytest.fixture
async def shopper(db: AsyncSession) -> User:
    return await make_user(db, email=EMAIL, password=PASSWORD)


async def _forgot(client: httpx.AsyncClient, email: str = EMAIL) -> httpx.Response:
    return await client.post(FORGOT, json={"email": email})


async def _reset(
    client: httpx.AsyncClient, token: str, password: str = NEW_PASSWORD
) -> httpx.Response:
    return await client.post(RESET, json={"token": token, "newPassword": password})


async def _login(client: httpx.AsyncClient, password: str) -> httpx.Response:
    return await client.post(LOGIN, json={"email": EMAIL, "password": password})


def _error_code(response: httpx.Response) -> str:
    code: str = response.json()["error"]["code"]
    return code


@pytest.fixture
def statements() -> Iterator[list[str]]:
    """Every SQL statement sent to the database while the test runs."""
    seen: list[str] = []

    def record(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        # The savepoint the test session wraps each commit in is numbered, and
        # the number is the only thing that differs between two requests.
        seen.append(re.sub(r"sa_savepoint_\d+", "sa_savepoint_N", statement))

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)


class TestAnUnknownAddress:
    """Answered exactly as a registered one, so the form lists nobody."""

    @staticmethod
    def _shape(response: httpx.Response) -> tuple[int, str, dict[str, str]]:
        headers = {k: v for k, v in response.headers.items() if k != "x-request-id"}
        return response.status_code, response.text, headers

    async def test_gets_the_same_response_after_the_same_queries(
        self,
        client: httpx.AsyncClient,
        fake_resend: FakeResend,
        shopper: User,
        statements: list[str],
    ) -> None:
        """Same status, body and headers - and the same SQL, statement for
        statement, which is what makes the timing the same: a lookup followed
        by a write only for a registered address would pass the response
        comparison and still answer later for that address."""
        await _forgot(client, "warm-up@example.ge")  # the first request's one-offs
        statements.clear()

        known = await _forgot(client, EMAIL)
        known_sql = list(statements)
        statements.clear()
        unknown = await _forgot(client, "ghost@example.ge")
        unknown_sql = list(statements)

        assert known.status_code == 200
        assert known.json() == {"ok": True}
        assert self._shape(unknown) == self._shape(known)
        assert unknown_sql == known_sql
        assert any("password_reset_tokens" in sql for sql in known_sql)  # not vacuous
        # The difference is only in what happens after the response.
        assert [b["to"] for b in fake_resend.bodies()] == [[EMAIL]]

    async def test_a_blocked_account_is_answered_as_no_account(
        self, client: httpx.AsyncClient, db: AsyncSession, fake_resend: FakeResend
    ) -> None:
        await make_user(db, email=EMAIL, password=PASSWORD, is_active=False)
        registered = await make_user(db, email="other@example.ge")

        blocked = await _forgot(client, EMAIL)
        active = await _forgot(client, registered.email)

        assert self._shape(blocked) == self._shape(active)
        assert [b["to"] for b in fake_resend.bodies()] == [["other@example.ge"]]

    async def test_the_email_goes_out_after_the_response(
        self, client: httpx.AsyncClient, fake_resend: FakeResend, shopper: User
    ) -> None:
        """The provider's round trip is not part of the answer's timing: the
        provider is held until the response has gone, and if the send ran
        first the response never would."""
        release = asyncio.Event()

        async def held(request: httpx.Request) -> httpx.Response:
            await release.wait()
            return await FakeResend.ok(request)

        fake_resend.answer = held

        status, still_sending = await respond_while_held(app, FORGOT, {"email": EMAIL}, release)

        assert status == 200
        assert still_sending
        assert len(fake_resend.requests) == 1


class TestTheEmail:
    async def test_carries_a_link_to_the_site_with_the_token_in_the_fragment(
        self, client: httpx.AsyncClient, fake_resend: FakeResend, shopper: User
    ) -> None:
        await _forgot(client, "  NINO@Example.GE ")

        [sent] = fake_resend.bodies()
        token = fake_resend.token()
        link = f"{SITE}/reset-password#token={token}"
        assert sent["to"] == [EMAIL]
        assert sent["from"] == SENDER
        assert sent["subject"] == "პაროლის აღდგენა — VoltBox"
        assert link in sent["text"].splitlines()
        assert f'href="{link}"' in sent["html"]
        assert "30 წუთი" in sent["text"]
        # A fragment, which no browser sends to a server - never the query.
        assert "?token=" not in sent["text"] + sent["html"]
        assert len(token) >= 43  # 256 bits
        [request] = fake_resend.requests
        assert request.headers["Idempotency-Key"].startswith("password-reset/")
        assert token not in request.headers["Idempotency-Key"]

    async def test_only_the_hash_is_stored(
        self, client: httpx.AsyncClient, db: AsyncSession, fake_resend: FakeResend, shopper: User
    ) -> None:
        await _forgot(client)
        token = fake_resend.token()

        row = await db.scalar(select(PasswordResetToken))
        assert row is not None
        assert row.token_hash != token
        assert token not in row.token_hash
        assert len(row.token_hash) == 64


class TestALink:
    async def test_works_once_and_then_fails(
        self, client: httpx.AsyncClient, fake_resend: FakeResend, shopper: User
    ) -> None:
        await _forgot(client)
        token = fake_resend.token()

        first = await _reset(client, token)
        second = await _reset(client, token, password="another-pass-8")

        assert first.status_code == 200, first.text
        assert second.status_code == 400
        assert _error_code(second) == "INVALID_RESET_TOKEN"
        # The first reset held; the second changed nothing.
        assert (await _login(client, NEW_PASSWORD)).status_code == 200
        assert (await _login(client, "another-pass-8")).status_code == 401
        assert (await _login(client, PASSWORD)).status_code == 401

    async def test_that_has_expired_fails(
        self, client: httpx.AsyncClient, db: AsyncSession, fake_resend: FakeResend, shopper: User
    ) -> None:
        await _forgot(client)
        token = fake_resend.token()
        await db.execute(
            update(PasswordResetToken).values(expires_at=func.now() - timedelta(seconds=1))
        )
        await db.flush()

        response = await _reset(client, token)

        assert response.status_code == 400
        assert _error_code(response) == "INVALID_RESET_TOKEN"
        assert (await _login(client, PASSWORD)).status_code == 200

    async def test_expires_in_under_an_hour(
        self, client: httpx.AsyncClient, db: AsyncSession, fake_resend: FakeResend, shopper: User
    ) -> None:
        await _forgot(client)

        row = await db.scalar(select(PasswordResetToken))
        assert row is not None
        assert row.expires_at - row.created_at == PASSWORD_RESET_TTL
        assert timedelta(hours=1) > PASSWORD_RESET_TTL

    async def test_an_unknown_token_fails_as_a_used_one_does(
        self, client: httpx.AsyncClient, shopper: User
    ) -> None:
        response = await _reset(client, "x" * 43)

        assert response.status_code == 400
        assert _error_code(response) == "INVALID_RESET_TOKEN"

    async def test_only_the_newest_works(
        self, client: httpx.AsyncClient, db: AsyncSession, fake_resend: FakeResend, shopper: User
    ) -> None:
        await _forgot(client)
        older = fake_resend.token()
        await _forgot(client)
        newer = fake_resend.token()

        assert (await _reset(client, older)).status_code == 400
        assert (await _reset(client, newer)).status_code == 200
        # One row per account, whatever was asked for.
        assert len((await db.scalars(select(PasswordResetToken))).all()) == 0

    async def test_dies_when_the_password_is_changed_another_way(
        self, client: httpx.AsyncClient, fake_resend: FakeResend, shopper: User
    ) -> None:
        await _forgot(client)
        token = fake_resend.token()
        session = (await _login(client, PASSWORD)).json()

        changed = await client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {session['token']}"},
            json={"currentPassword": PASSWORD, "newPassword": "changed-by-owner-3"},
        )

        assert changed.status_code == 200
        assert (await _reset(client, token)).status_code == 400
        assert (await _login(client, "changed-by-owner-3")).status_code == 200

    @pytest.mark.parametrize("password", ["short1", "password", "12345678", "x" * 129])
    async def test_refuses_a_password_registration_would_refuse_and_stays_usable(
        self, client: httpx.AsyncClient, fake_resend: FakeResend, shopper: User, password: str
    ) -> None:
        await _forgot(client)
        token = fake_resend.token()

        refused = await _reset(client, token, password=password)
        registration = await client.post(
            "/api/v1/auth/register",
            json={"firstName": "ნინო", "lastName": "კაპანაძე", "email": "new@example.ge"}
            | {"password": password},
        )

        assert refused.status_code == 400
        assert _error_code(refused) == "VALIDATION_ERROR"
        assert refused.json()["error"]["details"][0]["field"] == "newPassword"
        assert registration.status_code == 400  # the same rules, both ways
        # Refused before the link was touched, so it still works.
        assert (await _reset(client, token)).status_code == 200


class TestASuccessfulReset:
    async def test_ends_every_existing_session(
        self, client: httpx.AsyncClient, fake_resend: FakeResend, shopper: User
    ) -> None:
        """Both halves of each session, on each device: the access token and
        the refresh cookie."""
        devices = []
        for _ in range(2):
            session = await _login(client, PASSWORD)
            devices.append((session.json()["token"], client.cookies.get(COOKIE)))
        await _forgot(client)

        reset = await _reset(client, fake_resend.token())

        assert reset.status_code == 200, reset.text
        for access, refresh in devices:
            me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
            renewed = await client.post(
                "/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={refresh}"}
            )
            assert me.status_code == 401
            assert renewed.status_code == 401
        # And the new password opens a new one.
        assert (await _login(client, NEW_PASSWORD)).status_code == 200

    async def test_lifts_a_lock_left_by_failed_sign_ins(
        self, client: httpx.AsyncClient, db: AsyncSession, fake_resend: FakeResend, shopper: User
    ) -> None:
        await db.execute(
            update(User)
            .where(User.id == shopper.id)
            .values(locked_until=func.now() + timedelta(minutes=15))
        )
        await db.flush()
        await _forgot(client)

        await _reset(client, fake_resend.token())

        assert (await _login(client, NEW_PASSWORD)).status_code == 200


def _pad_to_cut_the_token(url_before_token: str) -> int:
    """How much to put before the link so the 200-character cut lands inside it."""
    return 200 - len(url_before_token) - 20


#: How a provider could refuse, some of them quoting the message back.
FAILURES: dict[str, Callable[[httpx.Request], httpx.Response]] = {
    "invalid key": lambda request: httpx.Response(401, json={"message": "API key is invalid"}),
    # A refusal that quotes the whole link back.
    "quotes the link": lambda request: httpx.Response(
        422, json={"message": f"Invalid link: {_link_in(json.loads(request.content)['text'])}"}
    ),
    # outbound keeps 200 characters of a reason; this puts the cut inside the token.
    "quotes the link, cut short": lambda request: httpx.Response(
        422,
        json={
            "message": "x" * _pad_to_cut_the_token(f"{SITE}/reset-password#token=")
            + " "
            + _link_in(json.loads(request.content)["text"])
        },
    ),
    "server error": lambda request: httpx.Response(500, json={"message": "Internal"}),
}


class TestTheToken:
    @pytest.mark.parametrize("outcome", ["sent", *FAILURES, "timeout", "sender raises"])
    async def test_is_in_no_log_and_no_response(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: httpx.AsyncClient,
        fake_resend: FakeResend,
        shopper: User,
        captured_logs: list[logging.LogRecord],
        outcome: str,
    ) -> None:
        if outcome in FAILURES:
            answer = FAILURES[outcome]

            async def failing(request: httpx.Request) -> httpx.Response:
                return answer(request)

            fake_resend.answer = failing
        elif outcome == "timeout":

            async def timing_out(request: httpx.Request) -> httpx.Response:
                raise httpx.ConnectTimeout("", request=request)

            fake_resend.answer = timing_out
        elif outcome == "sender raises":
            raising = RaisingSender()
            monkeypatch.setattr(mailer, "get_sender", lambda: raising)

        forgot = await _forgot(client)
        if outcome == "sender raises":
            [email] = raising.emails
            token = _token_in(email.text)
        else:
            token = fake_resend.token()
        reset = await _reset(client, token)
        replay = await _reset(client, token)

        # Formatted as production writes them, so the exception text and the
        # extra fields are searched along with the message.
        lines = [JsonFormatter().format(record) for record in captured_logs]
        # A prefix, so a token cut short is caught as well as a whole one.
        assert [line for line in lines if token[:16] in line] == []
        assert [line for line in lines if "#token=" in line and "<token>" not in line] == []
        for response in (forgot, reset, replay):
            assert token[:16] not in response.text
        assert reset.status_code == 200, reset.text
        assert replay.status_code == 400
        # Not vacuous: the reset routes were logged, and so was every failure,
        # without the address it was sent to.
        assert any('"path": "/api/v1/auth/reset-password"' in line for line in lines)
        if outcome != "sent":
            [error] = [r for r in captured_logs if r.levelno == logging.ERROR]
            assert "Password reset email" in error.getMessage()
            assert EMAIL not in error.getMessage()
        if outcome.startswith("quotes the link"):
            # The case is real: what outbound keeps of the provider's reason
            # holds the token - all of it, or when cut short only part, so that
            # replacing the whole token alone would leave that part in the line.
            quoted = outbound.reason_from_body(
                FAILURES[outcome](fake_resend.requests[0]), "message"
            )
            assert token[:16] in quoted
            assert (token in quoted) is (outcome == "quotes the link")
            assert "token=<token>" in _error_line(captured_logs)


def _error_line(records: list[logging.LogRecord]) -> str:
    [error] = [r for r in records if r.levelno == logging.ERROR]
    return error.getMessage()


class TestTheLimits:
    @pytest.fixture
    def counting(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An enabled limiter for the per-address count; the application's own
        is off in tests."""
        counting = build_limiter(enabled=True, storage_uri=MEMORY_STORAGE)
        monkeypatch.setattr(rate_limit, "limiter", counting)

    @pytest.mark.usefixtures("counting", "shopper")
    @pytest.mark.parametrize("address", [EMAIL, "ghost@example.ge"], ids=["known", "unknown"])
    async def test_an_address_gets_three_an_hour_registered_or_not(
        self, client: httpx.AsyncClient, fake_resend: FakeResend, address: str
    ) -> None:
        answers = [await _forgot(client, address) for _ in range(4)]
        other = await _forgot(client, "someone-else@example.ge")

        assert [a.status_code for a in answers] == [200, 200, 200, 429]
        assert _error_code(answers[-1]) == "TOO_MANY_RESET_REQUESTS"
        assert other.status_code == 200
        # Counted on the address in any spelling.
        again = await _forgot(client, address.upper())
        assert again.status_code == 429
        assert len(fake_resend.requests) == (3 if address == EMAIL else 0)

    @pytest.mark.usefixtures("fake_resend")
    async def test_an_ip_gets_five_a_minute_like_login(
        self, monkeypatch: pytest.MonkeyPatch, client: httpx.AsyncClient
    ) -> None:
        monkeypatch.setattr(limiter, "enabled", True)
        limiter.reset()
        try:
            answers = [await _forgot(client, f"user{n}@example.ge") for n in range(6)]
            resets = [await _reset(client, "x" * 43) for _ in range(6)]
        finally:
            limiter.reset()

        assert [a.status_code for a in answers] == [200] * 5 + [429]
        assert _error_code(answers[-1]) == "RATE_LIMITED"
        assert [r.status_code for r in resets] == [400] * 5 + [429]


class TestWhileEmailIsOff:
    @pytest.mark.parametrize(
        ("key", "sender"), [("", ""), (API_KEY, ""), ("", SENDER)], ids=["both", "sender", "key"]
    )
    async def test_no_link_is_promised_and_nothing_is_stored(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: httpx.AsyncClient,
        db: AsyncSession,
        fake_resend: FakeResend,
        shopper: User,
        key: str,
        sender: str,
    ) -> None:
        monkeypatch.setattr(settings, "resend_api_key", SecretStr(key))
        monkeypatch.setattr(settings, "email_from", sender)

        known = await _forgot(client, EMAIL)
        unknown = await _forgot(client, "ghost@example.ge")
        rules = await client.get("/api/v1/delivery")

        assert known.status_code == unknown.status_code == 503
        assert _error_code(known) == "PASSWORD_RESET_UNAVAILABLE"
        assert known.text == unknown.text
        assert await db.scalar(select(PasswordResetToken)) is None
        assert fake_resend.requests == []
        # What the storefront reads to hide the link.
        assert rules.json()["features"]["email"] is False
