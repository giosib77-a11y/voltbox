"""What happens when something breaks that nobody predicted.

Every other error in this API is deliberate: a validation failure, a 404, a
conflict. This file is about the other kind - a bug, a dropped connection, a
library raising something new after an upgrade - and the three things that have
to be true when one happens.

  · The caller learns nothing about the inside of the server.
  · The operator learns everything: the traceback, and which request it was.
  · The response is still a hardened response.

The second one is the one that was missing. `handle_unexpected` carried the
comment "დეტალები ლოგში რჩება" while logging nothing at all, and the access log
never saw the request either, because the exception passed straight through the
middleware that writes it. A 500 in production left no trace of any kind.

The third was missing too, for a subtler reason: Starlette's ServerErrorMiddleware
sits above every middleware the application adds, so a crash response is built
outside SecurityHeadersMiddleware and never passed through it.
"""

import json
import logging
from collections.abc import AsyncGenerator, Generator

import httpx
import pytest
from app.core.headers import BASE_HEADERS
from app.main import create_app
from fastapi import FastAPI

SECRET_IN_THE_MESSAGE = "connection to host db.internal failed for user postgres"


@pytest.fixture
def crashing_app() -> FastAPI:
    """A real application with one route that raises."""
    app = create_app()

    @app.get("/api/v1/_crash")
    async def _crash() -> None:
        raise RuntimeError(SECRET_IN_THE_MESSAGE)

    return app


@pytest.fixture
def captured_logs() -> Generator[list[logging.LogRecord]]:
    """Every record written during the test, collected from the root logger.

    Not `caplog`: under pytest 9 it captures nothing in this suite, and a test
    that silently observes an empty list would pass whether or not anything was
    ever logged - which is the exact bug this file exists to catch.
    """
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
async def crash_client(crashing_app: FastAPI) -> AsyncGenerator[httpx.AsyncClient]:
    # raise_app_exceptions=False: without it httpx re-raises the exception into
    # the test instead of letting the handler answer, and there is no response
    # to look at.
    transport = httpx.ASGITransport(app=crashing_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestWhatTheCallerSees:
    async def test_the_answer_is_a_plain_500(self, crash_client: httpx.AsyncClient) -> None:
        response = await crash_client.get("/api/v1/_crash")

        assert response.status_code == 500
        assert response.json() == {
            "error": {"code": "INTERNAL_ERROR", "message": "Internal server error", "details": None}
        }

    async def test_nothing_about_the_cause_reaches_them(
        self, crash_client: httpx.AsyncClient
    ) -> None:
        """An exception message can name a host, a user or a query."""
        response = await crash_client.get("/api/v1/_crash")

        body = response.text
        assert SECRET_IN_THE_MESSAGE not in body
        assert "Traceback" not in body
        assert "RuntimeError" not in body
        assert "db.internal" not in body

    async def test_the_response_is_still_hardened(self, crash_client: httpx.AsyncClient) -> None:
        """The crash path runs above SecurityHeadersMiddleware, so the handler
        has to set these itself. Every other status gets them from the
        middleware; this one used to get none of them."""
        response = await crash_client.get("/api/v1/_crash")

        for header, value in BASE_HEADERS.items():
            assert response.headers.get(header.lower()) == value, header

    async def test_it_carries_a_request_id_to_quote(self, crash_client: httpx.AsyncClient) -> None:
        response = await crash_client.get("/api/v1/_crash")

        assert response.headers.get("X-Request-ID")


class TestWhatTheOperatorSees:
    async def test_the_traceback_reaches_the_log(
        self, crash_client: httpx.AsyncClient, captured_logs: list[logging.LogRecord]
    ) -> None:
        await crash_client.get("/api/v1/_crash")

        errors = [r for r in captured_logs if r.levelno >= logging.ERROR]
        assert errors, "an unhandled exception was logged nowhere"
        record = errors[0]
        assert record.exc_info is not None, "logged without the traceback"
        assert SECRET_IN_THE_MESSAGE in str(record.exc_info[1])

    async def test_the_log_says_which_request_it_was(
        self, crash_client: httpx.AsyncClient, captured_logs: list[logging.LogRecord]
    ) -> None:
        """Without the path and the request id, a traceback in a busy log
        cannot be matched to the report that came in with it."""
        response = await crash_client.get("/api/v1/_crash?q=1")

        record = next(r for r in captured_logs if r.levelno >= logging.ERROR)
        fields = getattr(record, "extra_fields", {})
        assert fields.get("path") == "/api/v1/_crash"
        assert fields.get("method") == "GET"
        assert fields.get("request_id") == response.headers.get("X-Request-ID")

    async def test_the_failed_request_still_appears_in_the_access_log(
        self, crash_client: httpx.AsyncClient, captured_logs: list[logging.LogRecord]
    ) -> None:
        """A crash used to vanish from the access log completely: the exception
        passed through the middleware that writes the line, so a spike of 500s
        was invisible in the one place anybody looks first."""
        await crash_client.get("/api/v1/_crash")

        lines = [r for r in captured_logs if r.name == "voltbox.access"]
        assert lines, "the request never reached the access log"
        assert getattr(lines[-1], "extra_fields", {}).get("status") == 500

    async def test_the_log_line_is_still_json(self, crash_client: httpx.AsyncClient) -> None:
        """The formatter has to survive an exc_info payload - a traceback that
        breaks the JSON makes the whole line unparseable to a log collector."""
        from app.core.logging import JsonFormatter

        record = logging.LogRecord(
            "voltbox", logging.ERROR, __file__, 1, "unhandled exception", (), None
        )
        try:
            raise RuntimeError(SECRET_IN_THE_MESSAGE)
        except RuntimeError:
            import sys

            record.exc_info = sys.exc_info()

        line = JsonFormatter().format(record)
        parsed = json.loads(line)

        assert parsed["level"] == "ERROR"
        assert SECRET_IN_THE_MESSAGE in json.dumps(parsed)
