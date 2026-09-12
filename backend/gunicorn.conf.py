"""gunicorn-ის კონფიგი.

What it does: holds the server settings the Dockerfile used to pass as flags,
so that the one setting which must come from the environment - which proxy may
be believed about the client's IP - can be read and checked at startup.

Why it is a file and not CMD flags: an exec-form `CMD ["gunicorn", "--flag",
"${VAR}"]` does not expand `${VAR}` - there is no shell - so the proxy address
would have been passed through literally as the string "${FORWARDED_ALLOW_IPS}".
gunicorn reads FORWARDED_ALLOW_IPS from the environment by itself, which is
where the value comes from; this file exists to fail loudly when it is missing
in production instead of letting the default quietly take over again.

The default (`127.0.0.1`) is correct only when the proxy shares the container's
loopback. In a compose network or behind an ingress the proxy has its own
address, and with the default gunicorn refuses to believe `X-Forwarded-For`
from it - so every request looks like it came from the proxy, and one shared
rate-limit bucket covers the whole site. That is the bug this guards.
"""

import os

wsgi_app = "app.main:app"
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
bind = os.environ.get("BIND", "0.0.0.0:8000")

accesslog = "-"
errorlog = "-"
timeout = 60
graceful_timeout = 30

#: gunicorn's own default when FORWARDED_ALLOW_IPS is unset.
LOOPBACK_ONLY = "127.0.0.1"

PRODUCTION_ENVS = {"production", "staging"}

#: How many server connections this deployment may occupy in total. Supabase's
#: smaller instances allow 60, of which three are reserved for superusers and
#: roughly twenty are already held by Supabase's own services (PostgREST,
#: Realtime, Storage, GoTrue). The remainder is what is actually ours, and the
#: default leaves room for a migration and a psql session on top.
DEFAULT_CONNECTION_BUDGET = 30

#: Must match the defaults in app/core/config.py. Read from the environment
#: rather than imported, because this file runs before the application does.
DEFAULT_POOL_SIZE = 5
DEFAULT_MAX_OVERFLOW = 10


#: Lets gunicorn be run locally on purpose - `docker compose --profile full up`
#: does exactly that - without the check below turning it into a failure.
LOCAL_RUN_OPT_OUT = "ALLOW_NON_PRODUCTION_SERVER"


def _check_the_environment_is_named() -> None:
    """Refuse a deployment that never said it was one.

    `APP_ENV` defaults to `development`, and that default is the least safe
    value it can take: `/docs` and `/openapi.json` serve the whole admin API
    surface, the refresh cookie loses `Secure`, object storage falls back to a
    dict in one worker's memory, and both checks in this file return early
    without running. Five protections, all off, and the site still works - so
    nothing reports it.

    Forgetting an environment variable on a new host is the most ordinary
    deployment mistake there is, and gunicorn only ever runs in a deployment,
    so being unable to name the environment is the mistake itself.
    """
    configured = os.environ.get("APP_ENV", "").strip()

    if configured in PRODUCTION_ENVS:
        return

    if os.environ.get(LOCAL_RUN_OPT_OUT, "").strip() == "1":
        return

    named = configured or "not set"
    raise SystemExit(
        f"APP_ENV is {named}, but gunicorn only runs in a deployment. Left this "
        "way the API docs are public, the refresh cookie is not Secure, uploads "
        "go to process memory and the proxy and connection-pool checks are both "
        f"skipped. Set APP_ENV to one of {sorted(PRODUCTION_ENVS)}, or set "
        f"{LOCAL_RUN_OPT_OUT}=1 if this really is a local run."
    )


def _check_the_rate_limit_counters_are_shared() -> None:
    """Refuse several workers with nowhere shared to count.

    slowapi keeps its counters in the process when no Redis is configured, so
    each worker allows the full limit on its own: two workers turn "5 logins a
    minute" into ten, and the sixth attempt passes or fails depending on which
    one answers. That is the brute-force limit, quietly multiplied by a number
    nobody connected to it.

    One worker is the case where in-process counting is simply correct, so it is
    left alone rather than made to run a Redis it does not need.
    """
    if workers <= 1 or os.environ.get("REDIS_URL", "").strip():
        return

    raise SystemExit(
        f"{workers} workers and no REDIS_URL. Rate limit counters would live in "
        f"each worker separately, so every limit is {workers} times what it "
        "says - including the one on login attempts. Set REDIS_URL, or run a "
        "single worker with WEB_CONCURRENCY=1."
    )


def _check_the_hosts_are_named() -> None:
    """Refuse a deployment that answers to any Host it is given.

    `TRUSTED_HOSTS` defaults to `*`, and app/main.py reads that as "skip the
    middleware entirely" - so a deployed server answers a request claiming any
    hostname at all.

    Nothing in the application builds a URL from `Host` today, so this is a
    door rather than a hole. It is worth closing anyway: the thing that makes
    it a hole later is one line somewhere that does, and nobody writing that
    line will think to come back here.
    """
    configured = os.environ.get("TRUSTED_HOSTS", "").strip()

    if configured and configured != "*":
        return

    raise SystemExit(
        "TRUSTED_HOSTS is not set to real hostnames, so the Host header is not "
        "checked at all and the server answers to any name it is given. List "
        "the domains this API is served on, comma separated."
    )


def _check_connection_budget() -> None:
    """Refuse a worker count whose connection pools cannot all fit.

    Each worker owns a separate pool, so the ceiling is multiplied by the worker
    count - and raising WEB_CONCURRENCY is the first thing anyone does to a slow
    site. Past the limit Postgres refuses new connections, which surfaces as
    intermittent 500s under load rather than as anything pointing at the pool.
    """
    pool = int(os.environ.get("DB_POOL_SIZE", DEFAULT_POOL_SIZE))
    overflow = int(os.environ.get("DB_MAX_OVERFLOW", DEFAULT_MAX_OVERFLOW))
    budget = int(os.environ.get("DB_CONNECTION_BUDGET", DEFAULT_CONNECTION_BUDGET))

    if budget <= 0:  # an explicit opt-out, for a database that is not shared
        return

    ceiling = workers * (pool + overflow)
    if ceiling > budget:
        raise SystemExit(
            f"{workers} workers x (DB_POOL_SIZE {pool} + DB_MAX_OVERFLOW {overflow}) "
            f"= {ceiling} database connections, over the budget of {budget}. "
            "Lower WEB_CONCURRENCY or the pool settings, or raise "
            "DB_CONNECTION_BUDGET if the database really has room."
        )


def on_starting(server: object) -> None:
    """Refuse to start a production server that would mis-attribute every IP.

    An error rather than a warning: the failure is silent at runtime - the site
    works, rate limiting simply applies to everyone at once - so a warning in a
    startup log nobody reads is how this bug came back the first time.
    """
    configured = os.environ.get("FORWARDED_ALLOW_IPS", "").strip()

    if configured == "*":
        # Trusting every source means anyone can set X-Forwarded-For and pick
        # their own rate-limit bucket, which is worse than not trusting any.
        raise SystemExit(
            "FORWARDED_ALLOW_IPS='*' trusts X-Forwarded-For from any source, "
            "which lets a caller choose their own client IP. Name the proxy."
        )

    _check_the_environment_is_named()

    if os.environ.get("APP_ENV", "development") not in PRODUCTION_ENVS:
        return  # an opted-out local run; nothing below applies to it

    if not configured:
        raise SystemExit(
            "FORWARDED_ALLOW_IPS is not set. Behind a reverse proxy gunicorn "
            f"would trust only {LOOPBACK_ONLY}, so every request would be "
            "attributed to the proxy and the whole site would share one rate "
            "limit bucket. Set it to the proxy's address."
        )

    _check_the_hosts_are_named()
    _check_the_rate_limit_counters_are_shared()
    _check_connection_budget()
