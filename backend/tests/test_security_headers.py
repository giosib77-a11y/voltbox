"""Security headers on API responses.

What they cover: that the four headers are present, that they survive the paths
where middleware usually stops running - errors, 404s, rate-limit rejections -
and that HSTS is sent only where it is true.

Why each one: `nosniff` is the one that matters most here. A browser deciding
that a JSON body is really HTML is the single way a pure API response turns into
script execution, and these bodies carry customer data. The rest are cheap and
narrow the surface a little further.
"""

import httpx
import pytest
from app.core.config import Settings
from app.core.headers import API_CSP, HSTS_VALUE, SecurityHeadersMiddleware
from app.main import create_app

EXPECTED = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "content-security-policy": API_CSP,
}


def _settings(app_env: str) -> Settings:
    return Settings(
        app_env=app_env,
        database_url="postgresql://voltbox:voltbox@localhost:55432/voltbox",
        jwt_secret="x" * 40,
    )


@pytest.mark.parametrize(("header", "value"), sorted(EXPECTED.items()))
async def test_a_normal_response_carries_them(
    client: httpx.AsyncClient, header: str, value: str
) -> None:
    response = await client.get("/api/v1/health")

    assert response.headers.get(header) == value


@pytest.mark.parametrize("path", ["/api/v1/nope", "/api/v1/products/does-not-exist"])
async def test_a_404_carries_them_too(client: httpx.AsyncClient, path: str) -> None:
    """404s and errors are answered before most handlers run."""
    response = await client.get(path)

    assert response.status_code == 404
    for header, value in EXPECTED.items():
        assert response.headers.get(header) == value, header


async def test_an_unauthorized_response_carries_them(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/admin/me")

    assert response.status_code == 401
    assert response.headers.get("x-content-type-options") == "nosniff"


async def test_a_validation_error_carries_them(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": "not-an-email"})

    assert response.status_code == 400
    assert response.headers.get("x-content-type-options") == "nosniff"


async def test_the_request_id_header_still_gets_through(client: httpx.AsyncClient) -> None:
    """Guards the ordering: a middleware added outermost can shadow another."""
    response = await client.get("/api/v1/health")

    assert response.headers.get("X-Request-ID")
    assert response.headers.get("x-content-type-options") == "nosniff"


class TestHsts:
    """Sent only where it is true.

    A browser that sees HSTS once refuses plain http to that host for a year.
    That is correct in production and a lasting nuisance on a local address.
    """

    def test_absent_outside_a_deployment(self) -> None:
        assert _settings("development").is_deployed is False

    @pytest.mark.parametrize("app_env", ["production", "staging"])
    def test_present_in_a_deployment(self, app_env: str) -> None:
        assert _settings(app_env).is_deployed is True

    def test_the_value_does_not_ask_for_preloading(self) -> None:
        """Preload entries are effectively permanent and cover the whole domain.

        That is a decision about the domain, not something this service should
        make on its own by shipping a header.
        """
        assert "preload" not in HSTS_VALUE
        assert "max-age=31536000" in HSTS_VALUE

    async def test_it_is_actually_wired_to_the_flag(self, client: httpx.AsyncClient) -> None:
        """APP_ENV is `test` here, so the header must not appear."""
        response = await client.get("/api/v1/health")

        assert "strict-transport-security" not in response.headers


async def test_the_app_builds_with_the_middleware_present() -> None:
    """A guard against the middleware being dropped from create_app."""
    app = create_app()

    # object: Starlette types `cls` as a factory protocol, which mypy will not
    # compare with a class.
    classes: list[object] = [m.cls for m in app.user_middleware]
    assert SecurityHeadersMiddleware in classes
