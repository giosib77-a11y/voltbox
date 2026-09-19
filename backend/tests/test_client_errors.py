"""Crash reports from the browser.

A server error has been visible since section 13. A crash in a customer's
browser had nothing: the screen went blank and no record of it existed
anywhere. This endpoint is the smallest thing that puts those in the same log,
and everything it accepts was typed by a client nobody controls - so most of
what is tested here is what it refuses.
"""

import json
import logging
from collections.abc import Generator

import httpx
import pytest
from app.core.logging import JsonFormatter
from app.schemas.client_error import MAX_MESSAGE, MAX_STACK

PATH = "/api/v1/client-errors"


@pytest.fixture
def captured() -> Generator[list[logging.LogRecord]]:
    records: list[logging.LogRecord] = []

    class Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Collector(level=logging.DEBUG)
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)


def _fields(records: list[logging.LogRecord]) -> dict[str, object]:
    line = next(r for r in records if r.name == "voltbox.client")
    return getattr(line, "extra_fields", {})


async def test_a_report_reaches_the_log(
    client: httpx.AsyncClient, captured: list[logging.LogRecord]
) -> None:
    response = await client.post(
        PATH,
        json={"message": "Cannot read properties of undefined", "path": "/product/cable"},
    )

    assert response.status_code == 204
    fields = _fields(captured)
    assert fields["client_message"] == "Cannot read properties of undefined"
    assert fields["client_path"] == "/product/cable"


async def test_it_records_which_request_it_was(
    client: httpx.AsyncClient, captured: list[logging.LogRecord]
) -> None:
    response = await client.post(PATH, json={"message": "boom"})

    assert _fields(captured)["request_id"] == response.headers.get("X-Request-ID")


async def test_a_guest_may_report(client: httpx.AsyncClient) -> None:
    """A crash happens to somebody who is not signed in as easily as to
    somebody who is; requiring a token would lose exactly those reports."""
    response = await client.post(PATH, json={"message": "boom"})

    assert response.status_code == 204


class TestWhatItRefuses:
    async def test_an_empty_report(self, client: httpx.AsyncClient) -> None:
        assert (await client.post(PATH, json={"message": ""})).status_code == 400

    async def test_a_message_longer_than_the_cap(self, client: httpx.AsyncClient) -> None:
        response = await client.post(PATH, json={"message": "x" * (MAX_MESSAGE + 1)})

        assert response.status_code == 400

    async def test_a_stack_longer_than_the_cap(self, client: httpx.AsyncClient) -> None:
        response = await client.post(PATH, json={"message": "boom", "stack": "x" * (MAX_STACK + 1)})

        assert response.status_code == 400

    async def test_a_field_it_does_not_own(self, client: httpx.AsyncClient) -> None:
        response = await client.post(PATH, json={"message": "boom", "cookies": "..."})

        assert response.status_code == 400


class TestItCannotForgeALogEntry:
    """A log line is one line, and this one is written by a stranger."""

    async def test_a_newline_cannot_start_a_second_entry(
        self, client: httpx.AsyncClient, captured: list[logging.LogRecord]
    ) -> None:
        forged = 'boom\n{"level": "INFO", "message": "all clear"}'

        await client.post(PATH, json={"message": forged})

        message = _fields(captured)["client_message"]
        assert "\n" not in str(message)
        assert "all clear" in str(message), "flattened, not truncated - the report is still read"

    async def test_the_written_line_is_one_line_of_json(
        self, client: httpx.AsyncClient, captured: list[logging.LogRecord]
    ) -> None:
        await client.post(PATH, json={"message": 'boom\r\n{"level":"INFO"}'})

        record = next(r for r in captured if r.name == "voltbox.client")
        line = JsonFormatter().format(record)

        assert len(line.splitlines()) == 1
        assert json.loads(line)["level"] == "ERROR"
