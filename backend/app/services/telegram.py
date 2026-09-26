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
that URL in its own log line and exceptions; `redact` below is registered with
`outbound`, which filters the `httpx` logger and our ERROR line through it.
The retry and timeout policy is `outbound`'s too, shared with the customer's
confirmation email.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import quote
from uuid import UUID

import httpx

from app.core.config import settings
from app.services import outbound

logger = logging.getLogger("voltbox.telegram")

API_BASE = "https://api.telegram.org"

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


outbound.register_redactor(redact)


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
    """Send `text`. None on success, else why not."""
    # Quoted to stay one path segment: an unencoded `/` in a mistyped token
    # would move the request to another path, and out of reach of the redaction.
    token = quote(settings.telegram_bot_token.get_secret_value(), safe=":")
    return await outbound.post_with_retries(
        f"{API_BASE}/bot{token}/sendMessage",
        json={
            "chat_id": settings.telegram_chat_id.strip(),
            "text": text,
            "link_preview_options": {"is_disabled": True},
        },
        transport=_transport,
        # Telegram's own reason, e.g. "Unauthorized" or "Bad Request: chat not found".
        describe=lambda response: outbound.reason_from_body(response, "description"),
    )


async def notify_order_placed(notice: OrderNotice) -> None:
    """Background task: tell the owner, and never raise."""
    if not settings.telegram_enabled:
        return
    await outbound.send_quietly(
        lambda: _send(message_text(notice)),
        logger=logger,
        what="Telegram notification",
        order_number=notice.order_number,
    )
