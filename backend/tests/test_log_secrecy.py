"""What must never appear in a log line.

The standing rule for this project is that tokens, passwords and contact
details do not reach logs or error text. Section 13 added a `logger.exception`
to the unhandled-error handler, which is the right thing to do and also the
thing that made this file necessary: the traceback of a database error is not a
neutral object.

A SQLAlchemy exception carries the statement *and its bound parameters*, and on
the registration path those parameters are the customer's email and their
Argon2 password hash. Postgres then adds a DETAIL line naming the value that
collided. Both were being written out verbatim.

The application's own credentials are not here. They are kept out of every
repr by their type, which no formatter takes part in, and a repr reaches a
traceback or a debugger without being a log line - test_settings_secrecy.py.
"""

import hashlib
import hmac
import json
import logging
import re
from collections.abc import Generator

import httpx
import pytest
from app.core.config import settings
from app.core.logging import JsonFormatter
from app.db.session import engine
from app.main import create_app
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

EMAIL = "nino@example.ge"
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$SECRETSALT$SECRETHASHVALUE"


def _formatted(exc: BaseException) -> str:
    record = logging.LogRecord(
        "voltbox.error",
        logging.ERROR,
        __file__,
        1,
        "unhandled exception",
        (),
        (type(exc), exc, exc.__traceback__),
    )
    return JsonFormatter().format(record)


@pytest.fixture
async def collision(db: AsyncSession) -> IntegrityError:
    """A real unique violation, with real customer data in the statement."""
    await db.execute(
        text("create temporary table leak_probe (email text unique, password_hash text)")
    )
    await db.execute(
        text("insert into leak_probe values (:e, :p)"), {"e": EMAIL, "p": PASSWORD_HASH}
    )
    with pytest.raises(IntegrityError) as caught:
        await db.execute(
            text("insert into leak_probe values (:e, :p)"), {"e": EMAIL, "p": PASSWORD_HASH}
        )
    await db.rollback()
    return caught.value


class TestADatabaseErrorInTheLog:
    def test_the_engine_hides_bound_parameters(self) -> None:
        """The setting is the reason the hash below is absent; assert it
        directly so a future engine change cannot quietly undo the rest."""
        assert engine.sync_engine.hide_parameters is True

    async def test_the_password_hash_does_not_reach_the_log(
        self, collision: IntegrityError
    ) -> None:
        line = _formatted(collision)

        assert "SECRETHASH" not in line
        assert "argon2" not in line.lower()

    async def test_the_customer_email_does_not_reach_the_log(
        self, collision: IntegrityError
    ) -> None:
        """Postgres names the colliding value in its DETAIL line, which is not
        a bound parameter and survives hide_parameters."""
        line = _formatted(collision)

        assert EMAIL not in line

    async def test_but_the_line_still_says_what_broke(self, collision: IntegrityError) -> None:
        """Scrubbing is worth nothing if it leaves an operator with a mystery.
        The constraint, the column and the kind of failure all stay."""
        line = _formatted(collision)

        assert "UniqueViolation" in line
        assert "leak_probe_email_key" in line
        assert "Key (email)" in line, "the column name is the useful half"

    async def test_the_line_is_still_valid_json(self, collision: IntegrityError) -> None:
        parsed = json.loads(_formatted(collision))

        assert parsed["level"] == "ERROR"
        assert "exception" in parsed


CLIENT_IP = "203.0.113.77"


@pytest.fixture
def access_lines() -> Generator[list[str]]:
    """The `voltbox.access` lines as emitted - formatted by JsonFormatter, i.e.
    the exact text a log collector receives."""
    lines: list[str] = []

    class Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.name == "voltbox.access":
                lines.append(self.format(record))

    handler = Collector(level=logging.DEBUG)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    try:
        yield lines
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)


async def _health_from(address: str) -> None:
    transport = httpx.ASGITransport(app=create_app(), client=(address, 5000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/v1/health/live")).status_code == 200


async def _client_field(lines: list[str], address: str) -> str:
    await _health_from(address)
    return str(json.loads(lines[-1])["client"])


class TestTheAccessLogsClientField:
    """A-036: the limiter keys on `request.client.host`, and the log said nothing
    about it, so a wrong FORWARDED_ALLOW_IPS (every shopper = the proxy, one
    shared bucket) could not be seen. The raw address stays out of the log."""

    async def test_it_is_twelve_hex_characters(self, access_lines: list[str]) -> None:
        assert re.fullmatch(r"[0-9a-f]{12}", await _client_field(access_lines, CLIENT_IP))

    async def test_the_raw_address_is_nowhere_in_the_line(self, access_lines: list[str]) -> None:
        await _health_from(CLIENT_IP)

        assert access_lines, "nothing was logged, so the test proves nothing"
        assert all(CLIENT_IP not in line for line in access_lines)

    async def test_the_same_address_gives_the_same_value(self, access_lines: list[str]) -> None:
        first = await _client_field(access_lines, CLIENT_IP)
        second = await _client_field(access_lines, CLIENT_IP)

        assert first == second

    async def test_different_addresses_give_different_values(self, access_lines: list[str]) -> None:
        home = await _client_field(access_lines, CLIENT_IP)
        mobile = await _client_field(access_lines, "198.51.100.9")

        assert home != mobile

    async def test_another_jwt_secret_gives_another_value(
        self, access_lines: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        before = await _client_field(access_lines, CLIENT_IP)
        monkeypatch.setattr(settings, "jwt_secret", SecretStr("another-secret-" + "x" * 32))

        after = await _client_field(access_lines, CLIENT_IP)

        assert before != after

    async def test_it_is_not_a_plain_hash_of_the_address(self, access_lines: list[str]) -> None:
        """sha256 of an IPv4 address is reversed by trying all 2**32 of them."""
        value = await _client_field(access_lines, CLIENT_IP)

        assert value != hashlib.sha256(CLIENT_IP.encode()).hexdigest()[:12]

    async def test_the_key_is_derived_from_the_jwt_secret_not_the_secret_itself(
        self, access_lines: list[str]
    ) -> None:
        value = await _client_field(access_lines, CLIENT_IP)
        secret = settings.jwt_secret.get_secret_value().encode()
        direct = hmac.new(secret, CLIENT_IP.encode(), hashlib.sha256).hexdigest()[:12]
        key = hmac.new(secret, b"voltbox:access-log:client:v1", hashlib.sha256).digest()
        derived = hmac.new(key, CLIENT_IP.encode(), hashlib.sha256).hexdigest()[:12]

        assert value != direct, "the log pseudonym is keyed with the JWT key itself"
        assert value == derived

    async def test_it_is_the_address_the_rate_limiter_keys_on(
        self, access_lines: list[str]
    ) -> None:
        """Same source as slowapi's key function, so the log shows what the
        limiter sees: one value for all shoppers means one shared bucket."""
        from app.core.logging import client_pseudonym
        from slowapi.util import get_remote_address

        request = Request({"type": "http", "client": (CLIENT_IP, 1), "headers": []})

        assert await _client_field(access_lines, CLIENT_IP) == client_pseudonym(
            get_remote_address(request)
        )

    def test_a_request_without_a_client_gets_a_fixed_marker(self) -> None:
        from app.core.logging import NO_CLIENT, RequestContextMiddleware

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/x",
            "query_string": b"",
            "headers": [],
        }
        lines: list[logging.LogRecord] = []

        class Collector(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                lines.append(record)

        handler = Collector(level=logging.DEBUG)
        access = logging.getLogger("voltbox.access")
        access.addHandler(handler)
        previous = access.level
        access.setLevel(logging.INFO)
        try:
            RequestContextMiddleware._log(Request(scope), "rid", 200, 0.0)
        finally:
            access.removeHandler(handler)
            access.setLevel(previous)

        fields: dict[str, object] = getattr(lines[0], "extra_fields")  # noqa: B009
        assert fields["client"] == NO_CLIENT


class TestTheScrubberItself:
    """Directly, so the rule is pinned without needing a database round trip."""

    @pytest.mark.parametrize(
        ("detail", "kept"),
        [
            ("DETAIL:  Key (email)=(nino@example.ge) already exists.", "Key (email)"),
            ("DETAIL:  Key (phone)=(555123456) already exists.", "Key (phone)"),
            (
                "DETAIL:  Key (order_number)=(VB-20260913-1000) is still referenced.",
                "Key (order_number)",
            ),
        ],
    )
    def test_it_keeps_the_column_and_drops_the_value(self, detail: str, kept: str) -> None:
        from app.core.logging import scrub

        cleaned = scrub(detail)

        assert kept in cleaned
        assert not re.search(r"=\((?!…)[^)]", cleaned), cleaned

    @pytest.mark.parametrize(
        ("detail", "secret", "kept"),
        [
            # A value containing `)` must not leave its tail behind (A-068).
            ("DETAIL:  Key (name)=(Foo) Bar) already exists.", "Bar", "Key (name)=(…)"),
            # A column expression contains `)` itself.
            (
                "DETAIL:  Key (lower(email::text))=(a@b.com) already exists.",
                "a@b.com",
                "Key (lower(email::text))=(…)",
            ),
            # NOT NULL / CHECK violations quote the whole row (A-067).
            (
                "DETAIL:  Failing row contains (1, x@y.com, 555123456, $argon2id$abc).",
                "x@y.com",
                "Failing row contains (…)",
            ),
        ],
    )
    def test_it_cuts_the_value_to_the_end_of_the_line(
        self, detail: str, secret: str, kept: str
    ) -> None:
        from app.core.logging import scrub

        cleaned = scrub(f"violates constraint\n{detail}\nSTATEMENT: INSERT")

        assert secret not in cleaned
        assert kept in cleaned
        assert "violates constraint" in cleaned
        assert "STATEMENT: INSERT" in cleaned, "only the DETAIL line is cut"

    def test_it_leaves_an_ordinary_message_alone(self) -> None:
        from app.core.logging import scrub

        message = "connection to server at 127.0.0.1 port 5432 failed"

        assert scrub(message) == message
