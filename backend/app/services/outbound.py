"""What every order notice sent to a third-party HTTP API has in common.

What it does: the retry and timeout policy, the redaction of credentials from
the `httpx` logger and from our own ERROR line, and the wrapper that keeps a
background send from ever raising.
Where it fits: `telegram.py` (the owner's notice) and `order_email.py` (the
customer's confirmation) both send through here. Each one registers how to
find its own credential in a line of text; the rest is shared.

Notes: a send runs as a FastAPI background task after the order is committed
and the response is sent, so nothing here can fail or slow a checkout. What it
can do is lose a message - an outage longer than the retries, a bad credential,
a worker restarted between the response and the send - and each of those is
logged at ERROR.

httpx writes the request URL into an INFO line on the `httpx` logger for every
request, successful ones included, and into the message of the HTTPStatusError
that `raise_for_status` raises; a transport error keeps it on
`exc.request.url`. So nothing here raises for status or logs an exception
object, and the `httpx` logger gets a filter that runs every registered
redactor.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

#: Per attempt. The send runs after the response, so this bounds how long a
#: worker keeps a dead connection around, not how long a customer waits.
TIMEOUT = httpx.Timeout(5.0)

#: Pauses before the second and third attempt.
RETRY_DELAYS: tuple[float, ...] = (1.0, 3.0)

#: Worth another try: the provider throttling us, or the provider being down.
#: A 400, 401, 403 or 422 - a wrong address, a revoked key - fails the same way
#: every time.
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

Redactor = Callable[[str], str]

_redactors: list[Redactor] = []


def register_redactor(redactor: Redactor) -> None:
    """Add a way of taking a credential out of a line of text."""
    _redactors.append(redactor)


def redact(text: str) -> str:
    """`text` with every registered credential taken out."""
    for redactor in _redactors:
        text = redactor(text)
    return text


class _Redact(logging.Filter):
    """Rewrites a record on the `httpx` logger before any handler sees it."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        cleaned = redact(message)
        if cleaned != message:
            record.msg, record.args = cleaned, None
        return True


# At import, not in the lifespan: the checkout route imports the senders, and
# they import this, so the filter is in place before the first request can be
# sent, test runs included - they do not run the lifespan.
logging.getLogger("httpx").addFilter(_Redact())


async def post_with_retries(
    url: str,
    *,
    json: dict[str, Any],
    headers: dict[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None,
    describe: Callable[[httpx.Response], str],
) -> str | None:
    """POST `json`, retrying what is worth retrying. None on success, else why not.

    `describe` turns a refusal into the provider's own reason; `transport` is
    None for the real network, an httpx.MockTransport in the tests.
    """
    failure = ""
    async with httpx.AsyncClient(transport=transport, timeout=TIMEOUT) as client:
        for delay in (0.0, *RETRY_DELAYS):
            if delay:
                await asyncio.sleep(delay)
            try:
                response = await client.post(url, json=json, headers=headers)
            except httpx.HTTPError as exc:
                # The class says what happened; str() is often empty (a
                # ConnectTimeout's is) and never the URL, but redact anyway.
                failure = f"{type(exc).__name__}: {exc}".rstrip(": ")
                continue
            if response.is_success:
                return None
            failure = f"HTTP {response.status_code}: {describe(response)}"
            if response.status_code not in RETRYABLE_STATUSES:
                break
    return failure


def reason_from_body(response: httpx.Response, key: str) -> str:
    """The provider's own reason from a JSON body's `key`, or the status phrase."""
    try:
        body = response.json()
    except ValueError:
        return response.reason_phrase
    reason = body.get(key) if isinstance(body, dict) else None
    return str(reason)[:200] if reason else response.reason_phrase


async def send_quietly(
    send: Callable[[], Awaitable[str | None]],
    *,
    logger: logging.Logger,
    what: str,
    order_number: str,
    scrub: Redactor = lambda text: text,
) -> None:
    """Run `send` and never raise; a failure is one ERROR line.

    Anything escaping a background task is logged by the server with its
    traceback, and an httpx traceback can hold the URL. `scrub` takes out what
    this one message must not log beyond the credentials, a recipient's
    address for instance.
    """
    try:
        failure = await send()
    except Exception as exc:  # see the docstring
        failure = f"{type(exc).__name__}: {exc}"
    if failure is not None:
        logger.error(
            "%s for order %s was not sent: %s. The order is saved; see it in the admin panel.",
            what,
            order_number,
            scrub(redact(failure)),
        )
