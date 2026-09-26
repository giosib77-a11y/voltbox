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

Notes: slowapi calls the storage synchronously (`limiter.hit(...)`), so the
sync `redis://` scheme is the right one here and not `async+redis://`. The call
blocks the event loop for the round trip, which is sub-millisecond against a
co-located Redis and is the reason this must not point at a distant one.

ტესტებში გამორთულია: 5/წუთში ზღვარი ტესტების მესამე შესვლას დაბლოკავდა და
ჩავარდნები ლოგიკასთან კავშირს დაკარგავდნენ.
"""

import hashlib
import logging

from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

logger = logging.getLogger(__name__)

# ბრუტფორსის ზღვარი — შესვლასა და რეგისტრაციაზე მკაცრი
AUTH_RATE_LIMIT = "5/minute"

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
#: the number is guessable and the contact is the only secret - and a phone
#: number is not much of one. At the global 60/minute, ten thousand consecutive
#: numbers fall in about three hours, and what they open is a name, an address
#: and a purchase history.
#: Ten a minute leaves a real shopper untouched and makes that a day's work per
#: address. It is not a complete answer: a distributed attempt still gets
#: through, and only per-order-number attempt counting would close that.
LOOKUP_RATE_LIMIT = "10/minute"

#: Crash reports from the browser. Unauthenticated by necessity - a crash
#: happens to guests too - so the only thing standing between this endpoint and
#: a filled disk is the limit. Twenty a minute is far more than a broken page
#: produces and far less than a flood.
CLIENT_ERROR_RATE_LIMIT = "20/minute"

DEFAULT_LIMIT = "60/minute"

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
        default_limits=[DEFAULT_LIMIT],
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
    key = hashlib.sha256(address.strip().lower().encode("utf-8")).hexdigest()
    try:
        return limiter.limiter.hit(item, scope, key)
    except Exception:  # the store's own errors are not one type across backends
        logger.warning("Rate limit storage unreachable - counting %s in process memory", scope)
        return _address_fallback.hit(item, scope, key)
