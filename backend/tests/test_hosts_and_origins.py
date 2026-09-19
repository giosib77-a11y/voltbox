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
from app.core.config import Settings, settings
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


@pytest.mark.parametrize("value", ["", "   ", " , "])
async def test_a_list_naming_nothing_refuses_every_host(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """What gunicorn.conf.py tells the operator an empty TRUSTED_HOSTS does.
    Unset means `*` and no check; set to nothing means a check nothing passes."""
    monkeypatch.setattr(settings, "trusted_hosts", value)

    async with _client(create_app()) as client:
        response = await client.get("/api/v1/health", headers={"Host": "api.voltbox.ge"})

    assert response.status_code == 400
    assert response.text == "Invalid host header"


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


# ── the name Render gives the service ────────────────────────────────────────

ONRENDER = "voltbox-api.onrender.com"


def _from_the_environment() -> Settings:
    """Settings as the deployed process builds them, from the variables. No
    .env, so a developer's file cannot answer for the environment."""
    return Settings(
        _env_file=None,
        database_url="postgresql://voltbox:voltbox@localhost:55432/voltbox",
        jwt_secret="x" * 40,
    )


def test_the_name_is_read_from_the_variable_render_sets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Through the environment, because the variable's name is the contract: a
    field named one letter off passes every test that sets the attribute, and
    on Render trusts nothing."""
    monkeypatch.setenv("TRUSTED_HOSTS", "api.voltbox.ge")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", ONRENDER)

    assert _from_the_environment().trusted_host_list == ["api.voltbox.ge", ONRENDER]


def test_anywhere_but_render_the_list_is_trusted_hosts_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRUSTED_HOSTS", "api.voltbox.ge")
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)

    assert _from_the_environment().trusted_host_list == ["api.voltbox.ge"]


async def test_render_s_health_check_gets_in_and_a_stranger_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Until the custom domain is verified, Render's health check arrives with
    the onrender.com name as its Host."""
    monkeypatch.setattr(settings, "trusted_hosts", "api.voltbox.ge")
    monkeypatch.setattr(settings, "render_external_hostname", ONRENDER)

    statuses = {}
    async with _client(create_app()) as client:
        for host in (ONRENDER, "api.voltbox.ge", "elsewhere.example"):
            response = await client.get("/api/v1/nope", headers={"Host": host})
            statuses[host] = response.status_code

    assert statuses == {ONRENDER: 404, "api.voltbox.ge": 404, "elsewhere.example": 400}


@pytest.mark.parametrize(
    ("listed", "host", "status"),
    [
        # The local default. With the name added it would be `*` among names,
        # which app/main.py refuses to build.
        ("*", "anything.example", 404),
        # Naming nothing: gunicorn.conf.py tells the operator every request is
        # refused, and Render's own name is not an exception to that.
        ("", ONRENDER, 400),
    ],
)
async def test_the_name_joins_only_a_list_of_names(
    monkeypatch: pytest.MonkeyPatch, listed: str, host: str, status: int
) -> None:
    monkeypatch.setattr(settings, "trusted_hosts", listed)
    monkeypatch.setattr(settings, "render_external_hostname", ONRENDER)

    async with _client(create_app()) as client:
        response = await client.get("/api/v1/nope", headers={"Host": host})

    assert response.status_code == status


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
