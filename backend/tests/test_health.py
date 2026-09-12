"""Phase 0 — ჩონჩხის ტესტები: health, შეცდომის კონვერტი, request-id."""

import inspect
from pathlib import Path

import httpx
import pytest
from app.core.config import Settings
from app.main import create_app


async def test_health_reports_ok_and_database_up(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["version"]


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
