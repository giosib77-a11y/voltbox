"""TRUSTED_HOSTS and CORS_ORIGINS as the application reads them.

Three ways each setting could be wrong while the server started, served and
said nothing:

  · `voltbox.ge,*` installed the Host check and checked nothing - Starlette
    reads a `*` anywhere in the list as "accept any Host".
  · `https://voltbox.ge/` allowed no browser at all - CORSMiddleware compares
    origins exactly, and an Origin header never ends in a slash.
  · A refused Host left no line in the log. The check sits outside the access
    log, so listing the storefront's domain instead of the API's turned every
    request into a 400 with nothing anywhere naming the setting.

gunicorn.conf.py refuses the first in a deployment; its tests are with the
other startup checks in test_rate_limit.py.
"""

import logging
from collections.abc import Iterator

import httpx
import pytest
from app.core.config import settings
from app.core.hosts import LoggedTrustedHostMiddleware
from app.core.logging import JsonFormatter
from app.main import create_app
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send


@pytest.fixture
def captured_logs() -> Iterator[list[logging.LogRecord]]:
    """Every record written during the test, collected from the root logger.

    Not `caplog`, for the reason test_unhandled_errors.py gives: under pytest 9
    it captures nothing in this suite, and a test asserting an empty list would
    pass whether or not anything was logged.
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


def _host_lines(records: list[logging.LogRecord]) -> list[str]:
    """The Host check's lines, formatted as they reach the log."""
    return [JsonFormatter().format(r) for r in records if r.name == "voltbox.hosts"]


def _client(app: ASGIApp) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


# ── a wildcard among names ───────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["voltbox.ge,*", "*,api.voltbox.ge"])
def test_a_wildcard_among_names_refuses_to_build(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Built, it would answer to any Host while reading as if it checked some."""
    monkeypatch.setattr(settings, "trusted_hosts", value)

    with pytest.raises(RuntimeError, match="TRUSTED_HOSTS lists names beside"):
        create_app()


async def test_the_wildcard_alone_still_means_any_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """The local default, and what every other test in the suite runs on."""
    monkeypatch.setattr(settings, "trusted_hosts", "*")

    async with _client(create_app()) as client:
        response = await client.get("/api/v1/nope", headers={"Host": "anything.example"})

    assert response.status_code == 404


# ── naming the setting when a Host is refused ────────────────────────────────


async def test_the_storefront_domain_alone_refuses_the_api_and_says_why(
    monkeypatch: pytest.MonkeyPatch, captured_logs: list[logging.LogRecord]
) -> None:
    """The mistake docs/deployment.md measured: the storefront's names listed,
    the API's own left out. The answer stays Starlette's; the log names the
    setting."""
    monkeypatch.setattr(settings, "trusted_hosts", "voltbox.ge,www.voltbox.ge")

    async with _client(create_app()) as client:
        response = await client.get("/api/v1/health", headers={"Host": "api.voltbox.ge"})

    assert response.status_code == 400
    assert response.text == "Invalid host header"
    lines = _host_lines(captured_logs)
    assert len(lines) == 1, lines
    assert "TRUSTED_HOSTS" in lines[0]


async def test_the_line_does_not_carry_the_host_it_was_sent(
    monkeypatch: pytest.MonkeyPatch, captured_logs: list[logging.LogRecord]
) -> None:
    """A refused Host is one nobody configured - whoever sent it wrote it."""
    monkeypatch.setattr(settings, "trusted_hosts", "api.voltbox.ge")

    async with _client(create_app()) as client:
        await client.get("/api/v1/health", headers={"Host": "chosen-by-the-sender.example"})

    lines = _host_lines(captured_logs)
    assert len(lines) == 1, lines
    assert "chosen-by-the-sender" not in lines[0]


async def test_an_accepted_host_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, captured_logs: list[logging.LogRecord]
) -> None:
    monkeypatch.setattr(settings, "trusted_hosts", "api.voltbox.ge")

    async with _client(create_app()) as client:
        response = await client.get("/api/v1/nope", headers={"Host": "api.voltbox.ge"})

    assert response.status_code == 404
    assert _host_lines(captured_logs) == []


async def test_a_400_from_the_application_is_not_blamed_on_the_host(
    captured_logs: list[logging.LogRecord],
) -> None:
    """A line claiming TRUSTED_HOSTS is wrong sends the operator to the wrong
    setting, so it follows the Host decision, not the status code."""

    async def answers_400(scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse("no Idempotency-Key", status_code=400)(scope, receive, send)

    checked = LoggedTrustedHostMiddleware(answers_400, allowed_hosts=["api.voltbox.ge"])
    async with _client(checked) as client:
        response = await client.get("/", headers={"Host": "api.voltbox.ge"})

    assert response.status_code == 400
    assert _host_lines(captured_logs) == []


# ── an origin with a trailing slash ──────────────────────────────────────────


async def _preflight(origin: str) -> httpx.Response:
    async with _client(create_app()) as client:
        return await client.options(
            "/api/v1/health",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )


async def test_a_trailing_slash_still_lets_the_storefront_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "cors_origins", "https://voltbox.ge/")

    response = await _preflight("https://voltbox.ge")

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://voltbox.ge"


async def test_dropping_the_slash_does_not_make_a_wildcard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`*/` matched nothing before; with credentials allowed, a bare `*` would
    echo every Origin back as if it were the storefront."""
    monkeypatch.setattr(settings, "cors_origins", "*/")

    response = await _preflight("https://elsewhere.example")

    assert "access-control-allow-origin" not in response.headers
