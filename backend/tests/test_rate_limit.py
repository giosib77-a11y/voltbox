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
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.1.0.2")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("TRUSTED_HOSTS", "voltbox.ge")
    monkeypatch.setenv("CORS_ORIGINS", "https://voltbox.ge")
    conf = load_gunicorn_conf()

    conf.on_starting(None)


def test_a_local_run_that_says_so_needs_no_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing sits in front, so gunicorn's loopback default is already right."""
    conf = load_gunicorn_conf()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_NON_PRODUCTION_SERVER", "1")
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)

    conf.on_starting(None)


# ── connection budget ────────────────────────────────────────────────────────
#
# Each worker owns its own pool, so the number of database connections a
# deployment holds is `workers x (pool_size + max_overflow)`. Past what the
# server allows, Postgres refuses new connections: the site returns intermittent
# 500s under load, and nothing in the error points at the pool.


def _conf_with(monkeypatch: pytest.MonkeyPatch, **env: str) -> ModuleType:
    """A deployment that is valid except for whatever the caller overrides.

    `workers` is read at import, so the environment is set before loading.
    """
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.1.0.2")
    # Otherwise the shared-counter check below fires first and every test in
    # this section fails for a reason it is not about.
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("TRUSTED_HOSTS", "voltbox.ge")
    # Same reason: the origins check runs before the counters and the budget, so
    # without a valid value it would answer for every test in those sections.
    monkeypatch.setenv("CORS_ORIGINS", "https://voltbox.ge")
    for key in ("WEB_CONCURRENCY", "DB_POOL_SIZE", "DB_MAX_OVERFLOW", "DB_CONNECTION_BUDGET"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return load_gunicorn_conf()


def test_the_shipped_defaults_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two workers x 15 connections is exactly the budget, and must not trip."""
    _conf_with(monkeypatch).on_starting(None)


def test_more_workers_than_the_database_allows_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raising WEB_CONCURRENCY is the first thing anyone does to a slow site."""
    conf = _conf_with(monkeypatch, WEB_CONCURRENCY="4")

    with pytest.raises(SystemExit, match="60 database connections"):
        conf.on_starting(None)


def test_a_smaller_pool_lets_the_same_worker_count_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fix the message suggests has to actually work."""
    conf = _conf_with(monkeypatch, WEB_CONCURRENCY="4", DB_POOL_SIZE="3", DB_MAX_OVERFLOW="4")

    conf.on_starting(None)


def test_the_budget_can_be_raised_for_a_bigger_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conf = _conf_with(monkeypatch, WEB_CONCURRENCY="4", DB_CONNECTION_BUDGET="100")

    conf.on_starting(None)


def test_zero_opts_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """A database nobody else shares does not need this arithmetic."""
    conf = _conf_with(monkeypatch, WEB_CONCURRENCY="16", DB_CONNECTION_BUDGET="0")

    conf.on_starting(None)


def test_development_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """The check belongs to deployments; locally gunicorn is not what runs."""
    conf = _conf_with(monkeypatch, WEB_CONCURRENCY="16")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_NON_PRODUCTION_SERVER", "1")

    conf.on_starting(None)


# ── naming the environment ───────────────────────────────────────────────────
#
# APP_ENV defaults to `development`, which is the least safe value it can take:
# the API docs go public, the refresh cookie loses Secure, object storage falls
# back to process memory, and both checks above return early without running.
# gunicorn only runs in a deployment, so it is the right place to insist.


@pytest.mark.parametrize("app_env", [None, "", "development", "test"])
def test_a_server_that_cannot_name_its_environment_refuses(
    monkeypatch: pytest.MonkeyPatch, app_env: str | None
) -> None:
    conf = load_gunicorn_conf()
    monkeypatch.delenv("ALLOW_NON_PRODUCTION_SERVER", raising=False)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.1.0.2")
    if app_env is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", app_env)

    with pytest.raises(SystemExit, match="only runs in a deployment"):
        conf.on_starting(None)


def test_an_unset_environment_is_named_as_such_in_the_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reporting it as `development` would be a lie when nothing set it."""
    conf = load_gunicorn_conf()
    monkeypatch.delenv("ALLOW_NON_PRODUCTION_SERVER", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.1.0.2")

    with pytest.raises(SystemExit, match="APP_ENV is not set"):
        conf.on_starting(None)


@pytest.mark.parametrize("app_env", ["production", "staging"])
def test_a_named_deployment_passes(monkeypatch: pytest.MonkeyPatch, app_env: str) -> None:
    monkeypatch.delenv("ALLOW_NON_PRODUCTION_SERVER", raising=False)
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.1.0.2")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("TRUSTED_HOSTS", "voltbox.ge")
    monkeypatch.setenv("CORS_ORIGINS", "https://voltbox.ge")
    conf = load_gunicorn_conf()

    conf.on_starting(None)


# ── shared counters ──────────────────────────────────────────────────────────
#
# slowapi counts in the process when no Redis is configured, so each worker
# allows the full limit on its own. Two workers turn "5 logins a minute" into
# ten - the brute-force limit multiplied by a number nobody connected to it.


def test_several_workers_without_redis_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    conf = _conf_with(monkeypatch, WEB_CONCURRENCY="2")
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(SystemExit, match="no REDIS_URL"):
        conf.on_starting(None)


def test_one_worker_needs_no_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """In-process counting is simply correct with a single worker."""
    conf = _conf_with(monkeypatch, WEB_CONCURRENCY="1")
    monkeypatch.delenv("REDIS_URL", raising=False)

    conf.on_starting(None)


def test_several_workers_with_redis_are_fine(monkeypatch: pytest.MonkeyPatch) -> None:
    conf = _conf_with(monkeypatch, WEB_CONCURRENCY="2", REDIS_URL="redis://localhost:6379/0")

    conf.on_starting(None)


def test_a_blank_redis_url_does_not_count_as_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An env var set to whitespace is the shape a half-filled .env has."""
    conf = _conf_with(monkeypatch, WEB_CONCURRENCY="2", REDIS_URL="   ")

    with pytest.raises(SystemExit, match="no REDIS_URL"):
        conf.on_starting(None)


# ── naming the hosts ─────────────────────────────────────────────────────────
#
# `TRUSTED_HOSTS` defaults to `*`, which app/main.py reads as "skip the
# middleware entirely": a deployed server then answers a request claiming any
# hostname. Nothing builds a URL from `Host` today, so this is a door rather
# than a hole - and the line that turns it into one will be written by someone
# who does not know this check exists.


@pytest.mark.parametrize("value", [None, "", "*", "   "])
def test_a_deployment_that_answers_to_any_host_is_refused(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    conf = _conf_with(monkeypatch)
    if value is None:
        monkeypatch.delenv("TRUSTED_HOSTS", raising=False)
    else:
        monkeypatch.setenv("TRUSTED_HOSTS", value)

    with pytest.raises(SystemExit, match="TRUSTED_HOSTS"):
        conf.on_starting(None)


@pytest.mark.parametrize(
    "value", ["voltbox.ge,*", "*,voltbox.ge", "voltbox.ge , * ,www.voltbox.ge"]
)
def test_a_wildcard_among_names_is_refused(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Starlette reads a `*` anywhere in the list as "accept any Host", so the
    names beside it are checked no more than the wildcard alone is."""
    conf = _conf_with(monkeypatch, TRUSTED_HOSTS=value)

    with pytest.raises(SystemExit, match=r"TRUSTED_HOSTS contains '\*'"):
        conf.on_starting(None)


def test_a_subdomain_pattern_is_not_taken_for_the_wildcard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`*.voltbox.ge` matches subdomains, not every Host - refused by a check
    that looked for `*` inside an entry rather than an entry that is `*`."""
    conf = _conf_with(monkeypatch, TRUSTED_HOSTS="api.voltbox.ge,*.voltbox.ge")

    conf.on_starting(None)


def test_named_hosts_start_normally(monkeypatch: pytest.MonkeyPatch) -> None:
    conf = _conf_with(monkeypatch, TRUSTED_HOSTS="voltbox.ge,www.voltbox.ge")

    conf.on_starting(None)


def test_a_local_run_is_not_asked_for_hostnames(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is served to the internet, so there is no name to insist on."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_NON_PRODUCTION_SERVER", "1")
    monkeypatch.delenv("TRUSTED_HOSTS", raising=False)
    conf = load_gunicorn_conf()

    conf.on_starting(None)


# ── naming the origins ───────────────────────────────────────────────────────
#
# `CORS_ORIGINS` goes wrong in two opposite directions. With credentials allowed,
# `*` is not sent as `*`: Starlette echoes whatever Origin asked, so every site
# is treated as the storefront. And the default is the two localhost origins, so
# a deployment that forgets the variable starts, serves pages, and has every API
# call from the real domain refused by the browser.


@pytest.mark.parametrize("value", ["*", "https://voltbox.ge,*", "https://*.voltbox.ge"])
def test_a_deployment_that_lets_any_site_in_is_refused(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """A partial pattern is refused too: it is not supported and matches nothing."""
    conf = _conf_with(monkeypatch, CORS_ORIGINS=value)

    with pytest.raises(SystemExit, match="wildcard"):
        conf.on_starting(None)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_deployment_with_no_origins_is_refused(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    conf = _conf_with(monkeypatch)
    if value is None:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("CORS_ORIGINS", value)

    with pytest.raises(SystemExit, match="CORS_ORIGINS is not set"):
        conf.on_starting(None)


@pytest.mark.parametrize(
    "value",
    [
        "http://localhost:5173,http://localhost:4173",
        "https://voltbox.ge,http://127.0.0.1:5173",
        "localhost:5173",
    ],
)
def test_a_development_origin_left_in_production_is_refused(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """The first case is the shipped default, which is what forgetting it leaves."""
    conf = _conf_with(monkeypatch, CORS_ORIGINS=value)

    with pytest.raises(SystemExit, match="local development origin"):
        conf.on_starting(None)


def test_a_refusal_names_the_entry_and_not_its_userinfo(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rule app/core/logging.py keeps: the identifier stays, the value goes.

    One test across every way an entry gets named, because the promise is about
    the message rather than a branch - a password pasted along with an origin
    must not reach a deploy log from any of them, and the operator must still be
    told which entry to fix.
    """
    cases = [
        ("https://voltbox.ge,https://probe:s3cret@*.voltbox.ge", "(https://*.voltbox.ge)"),
        ("https://voltbox.ge,http://probe:s3cret@localhost:5173", "lists http://localhost:5173,"),
        # urlsplit cannot read it at all; the blank item still counts as one.
        ("https://voltbox.ge,,https://probe:s3cret@[*", "(entry 3)"),
        # The only `*` is in the password, so the origin alone would look valid.
        ("https://probe:s3cret*@voltbox.ge", "(entry 1)"),
    ]
    for value, kept in cases:
        conf = _conf_with(monkeypatch, CORS_ORIGINS=value)

        with pytest.raises(SystemExit) as refused:
            conf.on_starting(None)

        message = str(refused.value)
        assert "s3cret" not in message, message
        assert "probe" not in message, message
        assert "@" not in message, message
        assert kept in message, message


def test_named_origins_start_normally(monkeypatch: pytest.MonkeyPatch) -> None:
    conf = _conf_with(monkeypatch, CORS_ORIGINS="https://voltbox.ge,https://www.voltbox.ge")

    conf.on_starting(None)


def test_a_local_run_is_not_asked_for_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    """`docker compose --profile full up` runs gunicorn on the localhost default."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_NON_PRODUCTION_SERVER", "1")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173")
    conf = load_gunicorn_conf()

    conf.on_starting(None)
