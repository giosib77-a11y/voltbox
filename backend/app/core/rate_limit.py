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

import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

logger = logging.getLogger(__name__)

# ბრუტფორსის ზღვარი — შესვლასა და რეგისტრაციაზე მკაცრი
AUTH_RATE_LIMIT = "5/minute"

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
    storage_uri=storage_uri_for(settings.redis_url),
)
