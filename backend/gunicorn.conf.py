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

    if os.environ.get("APP_ENV", "development") not in PRODUCTION_ENVS:
        return

    if not configured:
        raise SystemExit(
            "FORWARDED_ALLOW_IPS is not set. Behind a reverse proxy gunicorn "
            f"would trust only {LOOPBACK_ONLY}, so every request would be "
            "attributed to the proxy and the whole site would share one rate "
            "limit bucket. Set it to the proxy's address."
        )
