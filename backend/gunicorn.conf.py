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
from urllib.parse import SplitResult, urlsplit

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

#: Hostnames that only ever mean "this machine". An origin built on one is a
#: development leftover - no customer's browser sends it.
LOCAL_ORIGIN_HOSTS = {"localhost", "127.0.0.1", "::1"}

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
    dict in one worker's memory, and on_starting skips every check after this
    one - the proxy, the hosts, the origins, the rate-limit counters and the
    connection budget. All of it off, and the site still works - so nothing
    reports it.

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
        "go to process memory and the rest of gunicorn.conf.py's startup checks "
        f"are skipped. Set APP_ENV to one of {sorted(PRODUCTION_ENVS)}, or set "
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

    Set but naming nothing - empty, blank, only commas - is the opposite
    failure, and the refusal has to say which one it is. app/main.py then
    installs the check with no names, so every request is a 400, the health
    check included. A message saying the Host goes unchecked would send the
    operator looking for the wrong thing.

    Read per entry, because a `*` beside real names is the same thing: Starlette
    treats a `*` anywhere in the list as "accept any Host", so `voltbox.ge,*`
    checks nothing while reading as if it checked voltbox.ge. Only an entry that
    is `*` on its own is refused - `*.voltbox.ge` is a pattern Starlette matches
    against subdomains, not a wildcard for every name.

    Nothing in the application builds a URL from `Host` today, so this is a
    door rather than a hole. It is worth closing anyway: the thing that makes
    it a hole later is one line somewhere that does, and nobody writing that
    line will think to come back here.
    """
    configured = os.environ.get("TRUSTED_HOSTS")
    if configured is None:
        raise SystemExit(
            "TRUSTED_HOSTS is not set, so it defaults to '*': the Host header is "
            "not checked at all and the server answers to any name it is given. "
            "List the domains this API is served on, comma separated."
        )

    hosts = [entry.strip() for entry in configured.split(",") if entry.strip()]
    if not hosts:
        raise SystemExit(
            "TRUSTED_HOSTS is set but names no host, so every request would be "
            "refused with 400 Invalid host header, the health check included. "
            "List the domains this API is served on, comma separated."
        )

    if "*" in hosts:
        raise SystemExit(
            "TRUSTED_HOSTS contains '*', which accepts any Host - Starlette reads "
            "a '*' anywhere in the list that way, whatever names are beside it. "
            "Remove it and list the domains this API is served on, comma separated."
        )


def _split_origin(origin: str) -> SplitResult | None:
    """An origin's parts, or None for a value urlsplit cannot read at all.

    Without a scheme urlsplit reads `localhost:5173` as scheme + path, so the
    host is put where it will be found. A bracket it cannot close - `[::1`, or a
    wildcard written as `[*]` - makes it raise instead, and a startup check that
    ends in a traceback says nothing about what to set.
    """
    try:
        return urlsplit(origin if "://" in origin else f"//{origin}")
    except ValueError:
        return None


def _name_the_origin(origin: str, position: int) -> str:
    """How a refusal names one CORS_ORIGINS entry: the origin, and nothing else.

    The rule app/core/logging.py applies to a database error - keep what
    identifies it, drop the value. An origin is a scheme, a host and a port, and
    those are public: the server hands them back to every browser. Anything else
    in the entry came from a pasted URL, where the part before `@` is a password
    and a path or query can be a token.

    Read from the text rather than `.hostname`, which drops the port, so a `*`
    written in the host or the port still shows. An entry that cannot be read,
    or whose only `*` sits in a part that is not printed, is named by position:
    printed raw it could carry the secret, and printed without its `*` it would
    look like a valid origin.
    """
    parts = _split_origin(origin)
    if parts is None:
        return f"entry {position}"

    host = parts.netloc.rpartition("@")[2]
    named = f"{parts.scheme}://{host}" if parts.scheme else host
    if not host or ("*" in origin and "*" not in named):
        return f"entry {position}"
    return named


def _check_the_origins_are_named() -> None:
    """Refuse a deployment whose browser allow-list is empty, a wildcard or local.

    Two failures with opposite symptoms. `*` looks merely permissive and is
    worse: with `allow_credentials=True` Starlette does not send `*`, it echoes
    whatever Origin asked, so every site is treated as the storefront. What
    keeps another *site* away from /auth/refresh today is the refresh cookie
    being SameSite=strict; a subdomain of the same site is not covered by that,
    since SameSite is site-based rather than origin-based. And
    REFRESH_COOKIE_SAMESITE is a setting: the day it becomes `none`, this is the
    only thing between any site and /auth/refresh.

    The other failure is quiet the opposite way. `CORS_ORIGINS` defaults to the
    two localhost origins, so a deployment that forgets it starts, serves the
    storefront, and has every API call from it refused by the browser.

    An entry urlsplit cannot read is refused for the same reason, and so is one
    that reads but is not an origin - no scheme, or a path. An Origin header is
    always scheme://host[:port], so such an entry matches no browser, and
    refusing it can never turn away a configuration that worked. An origin
    spelled otherwise than a browser sends it - capitals in the host, or the
    default port written out - is not refused: config.py rewrites it the way a
    browser spells it, so it matches (ASSUMPTIONS.md 8.12).
    """
    configured = os.environ.get("CORS_ORIGINS", "")
    # Numbered as written, blanks included, so "entry 3" is the third item
    # between commas - where an operator will count to.
    origins = [
        (position, entry.strip())
        for position, entry in enumerate(configured.split(","), start=1)
        if entry.strip()
    ]

    if not origins:
        raise SystemExit(
            "CORS_ORIGINS is not set, so no browser on the storefront's domain is "
            "allowed to call the API - the site loads and every request from it "
            "fails. Set it to the storefront's origin, for example "
            "https://voltbox.ge."
        )

    for position, origin in origins:
        if "*" in origin:
            named = _name_the_origin(origin, position)
            raise SystemExit(
                f"CORS_ORIGINS contains a wildcard ({named}). With credentials "
                "allowed the middleware does not send '*' - it echoes whatever "
                "Origin asked, so any site is treated as the storefront; and a "
                "pattern such as https://*.voltbox.ge is not supported at all and "
                "matches nothing. List the exact origins, comma separated."
            )

    for position, origin in origins:
        parts = _split_origin(origin)
        if parts is None:
            named = _name_the_origin(origin, position)
            raise SystemExit(
                f"CORS_ORIGINS has an entry that cannot be read as a URL ({named}), "
                "so no browser's Origin will ever match it - usually a '[' left "
                "open. Write it as scheme://host, for example https://voltbox.ge."
            )
        if parts.hostname in LOCAL_ORIGIN_HOSTS:
            named = _name_the_origin(origin, position)
            raise SystemExit(
                f"CORS_ORIGINS still lists {named}, a local development origin. "
                "No customer's browser sends it, and it usually means the real "
                "storefront origin was never added. Replace it with the "
                "storefront's origin."
            )
        # A lone trailing `/` is allowed: config.py drops it before the
        # middleware sees the list.
        if (
            not parts.scheme
            or not parts.hostname
            or "@" in parts.netloc
            or parts.path not in ("", "/")
            or parts.query
            or parts.fragment
        ):
            # By position: _name_the_origin would print https://voltbox.ge for
            # https://voltbox.ge/shop - the very origin the operator should write,
            # shown as the thing that is wrong.
            raise SystemExit(
                f"CORS_ORIGINS has an entry that is not an origin (entry {position}). "
                "A browser's Origin is scheme://host[:port] and nothing else, so "
                "an entry without a scheme, or with a path, query or login in it, "
                "matches no browser. Write it as scheme://host, for example "
                "https://voltbox.ge."
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
    _check_the_origins_are_named()
    _check_the_rate_limit_counters_are_shared()
    _check_connection_budget()
