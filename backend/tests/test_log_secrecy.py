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

import json
import logging
import re

import pytest
from app.core.logging import JsonFormatter
from app.db.session import engine
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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

    def test_it_leaves_an_ordinary_message_alone(self) -> None:
        from app.core.logging import scrub

        message = "connection to server at 127.0.0.1 port 5432 failed"

        assert scrub(message) == message
