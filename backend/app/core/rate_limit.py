"""მოთხოვნების სიხშირის შეზღუდვა.

What it does: builds the shared slowapi limiter, keyed on the real client IP and
counting in Redis when one is configured.

Two things have to be true for a limit to mean anything, and neither is free:

  1. **The key must be the client, not the proxy.** `get_remote_address` returns
     `request.client.host`, which Uvicorn fills in from `X-Forwarded-For` only
     for proxies gunicorn has been told to trust (`--forwarded-allow-ips`, see
     gunicorn.conf.py). Parsing the header here instead would mean trusting it
     from anyone, and a forged header would hand every caller their own bucket.
  2. **The counter must be shared.** In-process counters live in one worker, so
     the Dockerfile's two workers would allow twice the configured rate, and the
     sixth login attempt would pass or fail depending on which worker answered.

Redis being unreachable is handled deliberately: `in_memory_fallback_enabled`
keeps the same limits in process memory while the backend is down, and slowapi
retries the backend periodically. Not fail-open, which would remove the
brute-force limit exactly when something is already wrong; not fail-closed,
which would turn a Redis outage into "nobody can log in" for a shop. Degraded -
per worker instead of shared - is the honest middle, and it is logged.

Two kinds of limit exist. A route with its own `@limiter.limit` is checked by
the decorator, inside the route, and only against that limit. Every other route
is checked against DEFAULT_LIMIT (300/minute per client) by the
`enforce_default_limit` dependency, which `create_app` installs on the whole
application. Of those, only /health/live (Render's health check) is exempt from
all limits; /health, which queries the database, has its own HEALTH_RATE_LIMIT.
slowapi's own
`SlowAPIMiddleware` is not used for this: it finds the route handler by walking
`app.routes` for objects with an `.endpoint`, and under FastAPI 0.141 that list
holds `_IncludedRouter` objects without one, so the middleware silently skipped
every check (A-080) - 70 consecutive `GET /api/v1/categories` all answered 200.

Notes: slowapi calls the storage synchronously (`limiter.hit(...)`), so the
sync `redis://` scheme is the right one here and not `async+redis://`. The call
blocks the event loop for the round trip, which is sub-millisecond against a
co-located Redis and is the reason this must not point at a distant one.

ტესტებში გამორთულია: 5/წუთში ზღვარი ტესტების მესამე შესვლას დაბლოკავდა და
ჩავარდნები ლოგიკასთან კავშირს დაკარგავდნენ.
"""

import hashlib
import logging
import time
from math import ceil

from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from slowapi import Limiter
from slowapi.middleware import _should_exempt
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import settings

logger = logging.getLogger(__name__)

# ბრუტფორსის ზღვარი — შესვლასა და რეგისტრაციაზე მკაცრი
AUTH_RATE_LIMIT = "5/minute"

#: `POST /auth/refresh`. Not AUTH_RATE_LIMIT: that one is there to stop password
#: guessing, and refresh has no password to guess. It is spent with the
#: `HttpOnly; SameSite=strict; Path=/api/v1/auth` cookie, whose token is 384-bit
#: (`token_urlsafe(48)`) random and rotated on every use, so no rate makes it
#: guessable. What the endpoint does meet is many shoppers behind one address
#: (office NAT, mobile CGNAT) whose access tokens expire within the same
#: minutes; at five a minute the sixth got a 429, which the storefront treats
#: as a logout. Thirty a minute carries a crowd of real sessions and still caps
#: a script hammering the endpoint (each call is a database lookup and, on a
#: hit, a write).
#:
#: Still at AUTH_RATE_LIMIT, because they check or change a password or send an
#: email: login, register, forgot/reset password, change-password and profile
#: update.
REFRESH_RATE_LIMIT = "30/minute"

#: Password reset emails one address can be sent. The per-IP limit in front of
#: the endpoint is AUTH_RATE_LIMIT, like login; this one is for the mailbox on
#: the other end. Behind a botnet every request comes from a fresh IP, and
#: without a count on the address one inbox could be sent a link a minute, from
#: this shop's domain, for as long as someone cared to. Three an hour covers a
#: shopper whose first email went to spam and who asked twice more.
#:
#: Counted on the address whether or not it has an account, so an unknown
#: address runs out exactly as a known one does and the 429 says nothing about
#: who is registered.
RESET_EMAIL_ADDRESS_LIMIT = "3/hour"

#: Guest order lookup. Order numbers are VB-YYYYMMDD-NNNNN from one sequence, so
#: the number is guessable; the secret is the 256-bit (`token_urlsafe(32)`)
#: token issued with the order, which no rate makes guessable. This limit was
#: the only defence while the secret was the shopper's phone, and stays as a
#: cap on what any one address can make the endpoint do. Ten a minute leaves a
#: real shopper untouched.
LOOKUP_RATE_LIMIT = "10/minute"

#: Crash reports from the browser. Unauthenticated by necessity - a crash
#: happens to guests too - so the only thing standing between this endpoint and
#: a filled disk is the limit. Twenty a minute is far more than a broken page
#: produces and far less than a flood.
CLIENT_ERROR_RATE_LIMIT = "20/minute"

#: Checkout. A guest needs no account, an order takes its stock at once (it is
#: `pending` until an admin acts), the owner gets a Telegram message for each,
#: and the confirmation email goes to whatever address was typed. At the default
#: three hundred a minute one address could place orders for the whole catalogue
#: before anyone looked. Five a minute leaves a shopper who retries or buys twice
#: untouched; the daily ceiling stops the same script going slowly. An
#: Idempotency-Key replay counts as a request like any other.
ORDER_RATE_LIMIT = "5/minute;30/day"

#: Pricing a guest's cart (`POST /cart/quote`). The storefront calls it once
#: when a guest opens the cart or checkout, so thirty a minute is generous for
#: a shopper who edits the basket as they go, while a script walking the
#: catalogue id by id through this public endpoint meets the limit quickly.
CART_QUOTE_RATE_LIMIT = "30/minute"

#: Every route that has no `@limiter.limit` of its own: catalogue, cart, admin,
#: sitemap. One bucket per client address, shared by all of those routes.
#: Generous on purpose: a storefront page makes a handful of calls, an admin
#: screen a few dozen, and several shoppers can sit behind one NAT address;
#: three hundred a minute is far above that and still stops a script walking
#: the catalogue. A route with its own decorator keeps only that limit and is
#: not counted here (see `enforce_default_limit`).
DEFAULT_LIMIT = "300/minute"

#: `GET /health`, the one that asks the database (`SELECT 1`, a pool connection
#: per call). What polls it is an uptime monitor, once a minute or less; thirty
#: a minute leaves room for a person refreshing it by hand and still caps a
#: script that would otherwise take a connection from the pool on every request,
#: unthrottled. Its own limit, not DEFAULT_LIMIT: like any decorated route it is
#: counted here only. Render and the Dockerfile do not use it (see LIVENESS_PATH).
HEALTH_RATE_LIMIT = "30/minute"

#: Never counted, against any limit: Render's Health Check Path and the
#: Dockerfile's HEALTHCHECK poll it from one address every few seconds, and a
#: 429 there is read as "the instance is dead" and restarts it. It touches no
#: database and does no work, so there is nothing for a limit to protect. One
#: exact path, so no other route can ride on the exemption.
LIVENESS_PATH = f"{settings.api_v1_prefix}/health/live"

#: What slowapi gets when no Redis is configured: counters in this process only.
MEMORY_STORAGE = "memory://"


def storage_uri_for(redis_url: str) -> str:
    """The limiter's storage URI for a given REDIS_URL setting.

    Separate from the limiter so it can be asserted without standing up a
    Redis, and so the "no Redis configured" case has one obvious answer.
    """
    return redis_url.strip() or MEMORY_STORAGE


def build_limiter(*, enabled: bool, storage_uri: str) -> Limiter:
    """Construct a limiter. Split out of module scope so tests can vary it."""
    if storage_uri == MEMORY_STORAGE and enabled:
        logger.warning(
            "Rate limit counters are in process memory. With more than one "
            "worker each keeps its own, so the effective limit is multiplied. "
            "Set REDIS_URL to share them."
        )
    return Limiter(
        key_func=get_remote_address,
        # An application limit, not slowapi's `default_limits`: see
        # `enforce_default_limit` for why, and for what it is applied to.
        application_limits=[DEFAULT_LIMIT],
        enabled=enabled,
        storage_uri=storage_uri,
        # Keeps the same limits in process memory while Redis is unreachable
        # rather than dropping them or refusing every request.
        in_memory_fallback_enabled=True,
    )


limiter = build_limiter(
    enabled=settings.app_env != "test",
    storage_uri=storage_uri_for(settings.redis_url.get_secret_value()),
)


async def enforce_default_limit(request: Request) -> None:
    """Count the request against DEFAULT_LIMIT unless the route limits itself.

    Installed as an application-wide dependency, so it runs after routing and
    the matched route is in `request.scope["route"]` whatever the router tree
    looks like - which is what slowapi's middleware could not rely on (see the
    module docstring). Raises RateLimitExceeded, which `main.rate_limit_handler`
    turns into the 429 envelope with Retry-After.

    The check is slowapi's own `_check_request_limit` in its middleware mode,
    which is the call SlowAPIMiddleware would have made: the same key function,
    the same store, the in-memory fallback when Redis is down, and the same
    "ratelimit exceeded" WARNING (whose key `PseudonymiseRateLimitKey` replaces,
    so the raw address is not logged). The limit is registered as slowapi's
    *application* limit, one bucket per client address shared by all the routes
    this function counts (a per-route default would be scoped by URL, so
    `/products/<slug>` would give a script walking the catalogue a fresh bucket
    for every product). Middleware mode would add that bucket to a decorated
    route too, so `_should_exempt` - the middleware's own test - skips routes
    with `@limiter.limit`: they are counted against their own limit only.

    What is not counted: LIVENESS_PATH (`/health/live`) - `/health` is not
    exempt, it has its own HEALTH_RATE_LIMIT decorator and so skips this bucket
    like any decorated route; a CORS preflight, which CORSMiddleware
    answers before the router and never reaches here; and a path that matches no
    route (404), which costs one dictionary lookup and no database work. Nor is
    a body FastAPI cannot parse (malformed JSON or multipart, 400; an oversized
    one, 413): FastAPI reads and parses the body before it solves dependencies,
    so that request is answered before this function runs. A body that parses
    but fails schema validation (400) is counted, since the schema is checked
    while the dependencies are solved.
    """
    if not limiter.enabled or request.scope["path"] == LIVENESS_PATH:
        return
    endpoint = request.scope["route"].endpoint
    if _should_exempt(limiter, endpoint):
        return
    limiter._check_request_limit(request, endpoint, True)


#: Where an address is counted while the shared store cannot be reached and
#: slowapi has not yet switched to its own fallback. The same degraded middle
#: as the module docstring describes: per worker, not off.
_address_fallback = FixedWindowRateLimiter(MemoryStorage())


def hit_per_address(limit: str, *, scope: str, address: str) -> bool:
    """Count one request against `address`; False once `limit` is used up.

    slowapi keys a limit on something the request carries before its body is
    read, and an email address is in the body. So this counts directly in the
    limiter's own store - Redis when configured, shared by the workers - under
    the limiter's own on/off switch.

    The key is a SHA-256 of the normalised address, not the address: anything
    that can list the Redis keys would otherwise hold a list of everyone who
    asked for a reset, and slowapi's "ratelimit exceeded" WARNING names the key.
    """
    if not limiter.enabled:
        return True
    item = parse(limit)
    key = _address_key(address)
    try:
        return limiter.limiter.hit(item, scope, key)
    except Exception:  # the store's own errors are not one type across backends
        logger.warning("Rate limit storage unreachable - counting %s in process memory", scope)
        return _address_fallback.hit(item, scope, key)


def _address_key(address: str) -> str:
    return hashlib.sha256(address.strip().lower().encode("utf-8")).hexdigest()


def seconds_until_address_resets(limit: str, *, scope: str, address: str) -> int:
    """Whole seconds until `hit_per_address` counts `address` afresh; always >= 1.

    Asked of the store the way `main._retry_after_seconds` asks it for an IP
    limit. A store that cannot answer is tried through the in-process fallback
    (where a hit went while the store was down), and if that has nothing either
    the answer is the length of the whole window: possibly too long, never too
    short, and still a number.
    """
    item = parse(limit)
    window = max(1, int(item.get_expiry()))
    key = _address_key(address)
    for counter in (limiter.limiter, _address_fallback):
        try:
            reset_at = float(counter.get_window_stats(item, scope, key)[0])
            return max(1, min(window, ceil(reset_at - time.time())))
        except Exception:  # not one error type across backends, as in `hit_per_address`
            logger.warning("Rate limit window stats unavailable for %s", scope, exc_info=True)
    return window
