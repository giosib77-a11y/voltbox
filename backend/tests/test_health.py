"""Phase 0 — ჩონჩხის ტესტები: health, შეცდომის კონვერტი, request-id."""

import inspect
import logging
import re
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import httpx
import pytest
from app.core.config import Settings
from app.core.logging import request_id_from
from app.db.session import engine, get_db
from app.main import app, create_app
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def test_health_reports_ok_and_database_up(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["version"]


async def test_health_does_not_name_the_environment(client: httpx.AsyncClient) -> None:
    """A-046: an unauthenticated endpoint has no business saying production or staging.

    What it still says is what an uptime monitor reads: status, version, database.
    """
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert set(response.json()) == {"status", "version", "database"}


@pytest.fixture
async def client_without_database() -> AsyncGenerator[httpx.AsyncClient]:
    """The real driver against a port nothing listens on - a connection that fails
    the way an outage does, not a mock that raises whatever the test chose."""
    dead_engine = create_async_engine(engine.url.set(port=1), pool_pre_ping=True)
    sessions = async_sessionmaker(bind=dead_engine, expire_on_commit=False)

    async def unreachable_db() -> AsyncGenerator[AsyncSession]:
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = unreachable_db
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()
        await dead_engine.dispose()


async def test_health_is_503_when_the_database_is_down(
    client_without_database: httpx.AsyncClient,
) -> None:
    # uptime-მონიტორი მხოლოდ კოდს კითხულობს — 200 + "degraded" მისთვის "ცოცხალია"
    response = await client_without_database.get("/api/v1/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "down"
    assert set(body) == {"status", "version", "database"}  # no environment (A-046)


async def test_liveness_stays_200_when_the_database_is_down(
    client_without_database: httpx.AsyncClient,
) -> None:
    # Render ამ path-ზე ჩავარდნისას რესტარტავს; ბაზის გათიშვას რესტარტი ვერ შველის
    response = await client_without_database.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dockerfile_healthcheck_probes_liveness() -> None:
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")

    assert "/api/v1/health/live" in dockerfile


async def test_every_response_carries_request_id(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.headers["X-Request-ID"]


async def test_incoming_request_id_is_preserved(client: httpx.AsyncClient) -> None:
    # ლოგების კვალი front-იდან backend-ამდე რომ არ გაწყდეს
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "trace-me-123"})

    assert response.headers["X-Request-ID"] == "trace-me-123"


@pytest.fixture
def access_lines() -> Generator[list[logging.LogRecord]]:
    """The records of the access logger, which is where the request id is written."""
    records: list[logging.LogRecord] = []

    class Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.name == "voltbox.access":
                records.append(record)

    handler = Collector(level=logging.INFO)
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    try:
        yield records
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)


def _logged_request_ids(records: list[logging.LogRecord]) -> list[object]:
    return [getattr(r, "extra_fields", {}).get("request_id") for r in records]


GENERATED_ID = re.compile(r"[0-9a-f]{16}")

#: Just inside and just outside the accepted shape, and the kinds of value a
#: caller controls that a log line should not carry (A-046).
OK_IDS = [
    "abcdefgh",  # 8, the shortest
    "Ab-" * 21 + "z",  # 64, the longest
    "123e4567-e89b-12d3-a456-426614174000",  # a UUID
    "0123456789abcdef",  # what this API generates itself
]
BAD_IDS = [
    "abcdefg",  # 7, one short
    "a" * 65,  # 65, one long
    "x" * 300 + "<script>",  # the auditor's 308 characters
    "abc<script>def",
    "has space 12345678",
    "under_score_12345",
    "dots.are.not.ok.1",
    "line-one-12345678%0a",
]


@pytest.mark.parametrize("sent", OK_IDS)
async def test_a_well_formed_request_id_is_kept(
    client: httpx.AsyncClient, access_lines: list[logging.LogRecord], sent: str
) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": sent})

    assert response.headers["X-Request-ID"] == sent
    assert _logged_request_ids(access_lines) == [sent]


@pytest.mark.parametrize("sent", BAD_IDS)
async def test_a_malformed_request_id_is_replaced_in_the_header_and_the_log(
    client: httpx.AsyncClient, access_lines: list[logging.LogRecord], sent: str
) -> None:
    """The value came from outside and is echoed and logged, so a bad one is not."""
    response = await client.get("/api/v1/health", headers={"X-Request-ID": sent})

    returned = response.headers["X-Request-ID"]
    assert returned != sent
    assert GENERATED_ID.fullmatch(returned)
    assert _logged_request_ids(access_lines) == [returned]
    assert sent not in repr([getattr(r, "extra_fields", {}) for r in access_lines])


@pytest.mark.parametrize("header", [None, ""])
async def test_a_missing_or_empty_request_id_gets_a_generated_one(
    client: httpx.AsyncClient, header: str | None
) -> None:
    headers = {} if header is None else {"X-Request-ID": header}

    response = await client.get("/api/v1/health", headers=headers)

    assert GENERATED_ID.fullmatch(response.headers["X-Request-ID"])


@pytest.mark.parametrize("sent", ["abcdefgh\n", "abcdefgh\r\n", "\nabcdefgh", "abcdefgh "])
def test_a_trailing_newline_does_not_pass_the_pattern(sent: str) -> None:
    """`$` matches before a final newline; the pattern is a full match instead."""
    assert request_id_from(sent) != sent
    assert GENERATED_ID.fullmatch(request_id_from(sent))


async def test_an_error_response_carries_the_replacement_too(client: httpx.AsyncClient) -> None:
    """The 404 goes through errors.py's `_finish`, which copies request.state."""
    response = await client.get("/api/v1/nope", headers={"X-Request-ID": "x" * 300})

    assert response.status_code == 404
    assert GENERATED_ID.fullmatch(response.headers["X-Request-ID"])


async def test_unknown_route_uses_error_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "Not Found", "details": None}
    }


async def test_health_response_is_camel_case(client: httpx.AsyncClient) -> None:
    # frontend camelCase-ს ელოდება; snake_case-ის გაპარვა მდუმარე ბაგია
    body = await client.get("/api/v1/health")

    assert "_" not in "".join(body.json().keys())


class TestApiDocsExposure:
    """`/docs` and `/openapi.json` must be off wherever the API is reachable.

    The schema lists every admin route with its request shape - a map of the
    surface worth attacking. Staging counts: it is a deployment with a public
    address, and the only thing it lacks is real customers.
    """

    @pytest.mark.parametrize("app_env", ["production", "staging"])
    def test_hidden_in_a_deployment(self, app_env: str) -> None:
        settings = Settings(
            app_env=app_env,
            database_url="postgresql://voltbox:voltbox@localhost:55432/voltbox",
            jwt_secret="x" * 40,
        )

        assert settings.is_deployed is True

    @pytest.mark.parametrize("app_env", ["development", "test"])
    def test_available_locally(self, app_env: str) -> None:
        settings = Settings(
            app_env=app_env,
            database_url="postgresql://voltbox:voltbox@localhost:55432/voltbox",
            jwt_secret="x" * 40,
        )

        assert settings.is_deployed is False

    def test_the_app_actually_wires_it_to_the_docs_urls(self) -> None:
        """The property is only worth anything if create_app reads it."""
        source = Path(inspect.getfile(create_app)).read_text(encoding="utf-8")

        assert "openapi_url=None if settings.is_deployed" in source
        assert "docs_url=None if settings.is_deployed" in source
