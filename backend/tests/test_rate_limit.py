"""Rate limiting.

What it covers: the two properties that make a limit real, both of which used
to fail silently - the site kept working, the limit simply applied to everyone
at once, or allowed twice what was configured.

  1. The key is the client, not a header the client controls. `X-Forwarded-For`
     is only believable from a proxy gunicorn has been told to trust, and it is
     Uvicorn that turns it into `request.client.host`. Reading the header here
     would mean honouring it from anyone.
  2. The counter is shared. Two gunicorn workers with in-process counters give
     each caller two buckets.

The limiter under test is built by `build_limiter`, not the application's own:
that one is disabled in the test environment, because a 5/minute auth limit
would otherwise reject the third login any test suite performs.

Needs the Redis from docker-compose (`docker compose up -d redis`). The
cross-worker assertion is not provable without it, which is the point.
"""

import importlib.util
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from app.core.rate_limit import MEMORY_STORAGE, build_limiter, storage_uri_for
from fastapi import FastAPI, Request
from httpx import ASGITransport
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import JSONResponse, PlainTextResponse, Response

#: Database 1, so a developer's own Redis keys are never touched.
REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:56379/1")

LIMIT = "5/minute"
OVER = 6


def _too_many(request: Request, exc: Exception) -> Response:
    return JSONResponse({"error": {"code": "RATE_LIMITED"}}, status_code=429)


def build_app(limiter: Limiter) -> FastAPI:
    """A one-route app carrying the limiter under test."""
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _too_many)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/ping")
    @limiter.limit(LIMIT)
    async def ping(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    return app


def client_from(app: FastAPI, ip: str) -> httpx.AsyncClient:
    """A client whose connection really originates from `ip`.

    ASGITransport fills `request.client` from this, which is where Uvicorn
    would put the address it resolved from the proxy chain.
    """
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, client=(ip, 50000)), base_url="http://test"
    )


@pytest.fixture
async def redis_limiter() -> AsyncIterator[Limiter]:
    """A limiter on the shared store, with the counters cleared first."""
    limiter = build_limiter(enabled=True, storage_uri=REDIS_URL)
    limiter.reset()
    yield limiter
    limiter.reset()


def test_without_redis_the_counters_stay_in_this_process() -> None:
    assert storage_uri_for("") == MEMORY_STORAGE
    assert storage_uri_for("   ") == MEMORY_STORAGE


def test_a_configured_redis_becomes_the_store() -> None:
    assert storage_uri_for("  redis://cache:6379/0  ") == "redis://cache:6379/0"


async def test_a_forged_forwarded_header_cannot_buy_a_fresh_bucket(
    redis_limiter: Limiter,
) -> None:
    """One caller, a new X-Forwarded-For each time, still one bucket.

    If the key function parsed the header, every request would look like a
    different client and the limit would never be reached.
    """
    app = build_app(redis_limiter)
    statuses = []
    async with client_from(app, "203.0.113.7") as client:
        for n in range(OVER):
            response = await client.get("/ping", headers={"X-Forwarded-For": f"10.0.0.{n}"})
            statuses.append(response.status_code)

    assert statuses == [200] * (OVER - 1) + [429]


async def test_two_clients_do_not_share_a_bucket(redis_limiter: Limiter) -> None:
    """The regression the whole task is about: one limit for the entire site."""
    app = build_app(redis_limiter)

    async with client_from(app, "198.51.100.1") as first:
        for _ in range(OVER - 1):
            assert (await first.get("/ping")).status_code == 200
        assert (await first.get("/ping")).status_code == 429

    # A different visitor arrives to a bucket of their own.
    async with client_from(app, "198.51.100.2") as second:
        assert (await second.get("/ping")).status_code == 200


async def test_two_workers_share_one_counter_through_redis(redis_limiter: Limiter) -> None:
    """Two limiters on one Redis behave as one, which is what a worker is.

    Alternating between them is the case that mattered: with in-process
    counters each would allow the full five, so the sixth request passed or
    failed depending on which worker happened to answer it.
    """
    workers = [
        build_app(redis_limiter),
        build_app(build_limiter(enabled=True, storage_uri=REDIS_URL)),
    ]

    statuses = []
    for n in range(OVER):
        async with client_from(workers[n % 2], "192.0.2.50") as client:
            statuses.append((await client.get("/ping")).status_code)

    assert statuses == [200] * (OVER - 1) + [429]


def load_gunicorn_conf() -> ModuleType:
    """Import gunicorn.conf.py, which sits at the backend root, not in a package."""
    path = Path(__file__).resolve().parents[1] / "gunicorn.conf.py"
    spec = importlib.util.spec_from_file_location("voltbox_gunicorn_conf", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("app_env", ["production", "staging"])
def test_a_production_server_refuses_to_start_without_a_named_proxy(
    monkeypatch: pytest.MonkeyPatch, app_env: str
) -> None:
    """An error, not a warning.

    The failure is invisible at runtime - the site serves fine and every caller
    simply shares one rate-limit bucket - so a warning in a startup log is how
    this came back the first time.
    """
    conf = load_gunicorn_conf()
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)

    with pytest.raises(SystemExit, match="FORWARDED_ALLOW_IPS"):
        conf.on_starting(None)


def test_trusting_every_source_is_refused_outright(monkeypatch: pytest.MonkeyPatch) -> None:
    """`*` is worse than the default: it lets a caller pick their own IP."""
    conf = load_gunicorn_conf()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")

    with pytest.raises(SystemExit, match="any source"):
        conf.on_starting(None)


def test_a_named_proxy_starts_normally(monkeypatch: pytest.MonkeyPatch) -> None:
    conf = load_gunicorn_conf()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.1.0.2")

    conf.on_starting(None)


def test_local_development_needs_no_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing sits in front, so gunicorn's loopback default is already right."""
    conf = load_gunicorn_conf()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)

    conf.on_starting(None)
