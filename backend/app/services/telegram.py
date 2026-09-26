"""Telling the shop owner on Telegram that an order was placed.

What it does: sends one message - order number, goods, delivery fee, total, item
count and a link to the order in the admin panel - to TELEGRAM_CHAT_ID through
the Bot API.
Where it fits: the checkout route schedules `notify_order_placed` as a
background task after the order has been committed, so the order never waits
for Telegram and never fails because of it.

Notes: a lost message is possible - a Telegram outage longer than the retries,
a bad token, a worker restarted between the response and the send. Each of
those is logged at ERROR, and the admin panel stays the list of orders to
trust. No customer name, phone or address is sent: those stay in the admin.

The token is part of the URL path (`/bot<token>/sendMessage`), and httpx puts
that URL in two places by itself: an INFO line on the `httpx` logger for every
request, successful ones included, and the message of the HTTPStatusError that
`raise_for_status` raises. A transport error keeps it on `exc.request.url`.
So nothing here raises for status or logs an exception object, and the `httpx`
logger gets a filter that redacts the path segment.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import quote
from uuid import UUID

import httpx

from app.core.config import settings

logger = logging.getLogger("voltbox.telegram")

API_BASE = "https://api.telegram.org"

#: Per attempt. The send runs after the response, so this bounds how long a
#: worker keeps a dead connection around, not how long a customer waits.
TIMEOUT = httpx.Timeout(5.0)

#: Pauses before the second and third attempt.
RETRY_DELAYS: tuple[float, ...] = (1.0, 3.0)

#: Worth another try: Telegram throttling us, or Telegram being down. A 400,
#: 401 or 403 - wrong chat id, revoked token, bot blocked - fails the same way
#: every time.
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

#: The token as it appears in any URL httpx prints - matched by position, not
#: by value, because httpx percent-encodes a token pasted with a space in it,
#: and the encoded form would slip past a search for the configured value.
_TOKEN_IN_URL = re.compile(r"(api\.telegram\.org/bot)[^/\s'\"]*")

#: Tests put an httpx.MockTransport here; None is the real network.
_transport: httpx.AsyncBaseTransport | None = None


def redact(text: str) -> str:
    """`text` with the bot token removed, wherever a Telegram URL carries it."""
    text = _TOKEN_IN_URL.sub(r"\1<redacted>", text)
    token = settings.telegram_bot_token.get_secret_value()
    return text.replace(token, "<redacted>") if token else text


class _RedactToken(logging.Filter):
    """Rewrites a record on the `httpx` logger before any handler sees it."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        cleaned = redact(message)
        if cleaned != message:
            record.msg, record.args = cleaned, None
        return True


# At import, not in the lifespan: the checkout route imports this module, so
# the filter is in place before the first request can be sent, test runs
# included - they do not run the lifespan.
logging.getLogger("httpx").addFilter(_RedactToken())


@dataclass(frozen=True)
class OrderNotice:
    """What the message says, copied out of the order before the session closes."""

    order_id: UUID
    order_number: str
    subtotal: Decimal
    shipping: Decimal
    total: Decimal
    currency: str
    item_count: int


def log_configuration() -> None:
    """Say once, at startup, whether notifications are on."""
    token = bool(settings.telegram_bot_token.get_secret_value())
    chat = bool(settings.telegram_chat_id.strip())
    if token and chat:
        logger.info("Telegram order notifications are on")
    elif token or chat:
        # Half set is a mistake, not a choice.
        missing = "TELEGRAM_CHAT_ID" if token else "TELEGRAM_BOT_TOKEN"
        logger.warning("Telegram order notifications are off: %s is not set", missing)
    else:
        logger.info(
            "Telegram order notifications are off: TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHAT_ID are not set"
        )


def message_text(notice: OrderNotice) -> str:
    link = f"{settings.site_url.rstrip('/')}/admin/orders/{notice.order_id}"
    return (
        f"ახალი შეკვეთა {notice.order_number}\n"
        f"პროდუქტები: {notice.subtotal:.2f} {notice.currency}\n"
        f"მიწოდება: {notice.shipping:.2f} {notice.currency}\n"
        f"ჯამი: {notice.total:.2f} {notice.currency}\n"
        f"ნივთები: {notice.item_count}\n"
        f"{link}"
    )


async def _send(text: str) -> str | None:
    """Send `text`, retrying what is worth retrying. None on success, else why not."""
    # Quoted to stay one path segment: an unencoded `/` in a mistyped token
    # would move the request to another path, and out of reach of the redaction.
    token = quote(settings.telegram_bot_token.get_secret_value(), safe=":")
    url = f"{API_BASE}/bot{token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id.strip(),
        "text": text,
        "link_preview_options": {"is_disabled": True},
    }

    failure = ""
    async with httpx.AsyncClient(transport=_transport, timeout=TIMEOUT) as client:
        for delay in (0.0, *RETRY_DELAYS):
            if delay:
                await asyncio.sleep(delay)
            try:
                response = await client.post(url, json=payload)
            except httpx.HTTPError as exc:
                # The class says what happened; str() is often empty (a
                # ConnectTimeout's is) and never the URL, but redact anyway.
                failure = f"{type(exc).__name__}: {exc}".rstrip(": ")
                continue
            if response.is_success:
                return None
            failure = f"HTTP {response.status_code}: {_description(response)}"
            if response.status_code not in RETRYABLE_STATUSES:
                break
    return failure


def _description(response: httpx.Response) -> str:
    """Telegram's own reason, e.g. "Unauthorized" or "Bad Request: chat not found"."""
    try:
        body = response.json()
    except ValueError:
        return response.reason_phrase
    reason = body.get("description") if isinstance(body, dict) else None
    return str(reason)[:200] if reason else response.reason_phrase


async def notify_order_placed(notice: OrderNotice) -> None:
    """Background task: tell the owner, and never raise.

    Anything escaping a background task is logged by the server with its
    traceback, and an httpx traceback can hold the URL.
    """
    if not settings.telegram_enabled:
        return
    try:
        failure = await _send(message_text(notice))
    except Exception as exc:  # see the docstring
        failure = f"{type(exc).__name__}: {exc}"
    if failure is not None:
        logger.error(
            "Telegram notification for order %s was not sent: %s. "
            "The order is saved; see it in the admin panel.",
            notice.order_number,
            redact(failure),
        )
