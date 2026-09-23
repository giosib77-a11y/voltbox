"""Phase 0 — ჩონჩხის ტესტები: health, შეცდომის კონვერტი, request-id."""

import inspect
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
from app.core.config import Settings
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
