"""Sending one email through a provider's HTTP API.

What it does: `EmailSender` is the whole interface - send one message, answer
None or why not. `ResendSender` implements it on Resend's `POST /emails`.
Where it fits: `order_email.py` builds the message and calls `get_sender()`;
nothing else knows which provider is behind it. Swapping providers is a new
class here and a new `get_sender`.

Notes: the API key travels in the Authorization header, which httpx does not
log, but it is registered with `outbound` all the same - a provider that
quoted the request back in an error would otherwise put it in our ERROR line.
Retries, timeouts and the "never raise" wrapper are `outbound`'s, shared with
the Telegram notice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import settings
from app.services import outbound

RESEND_URL = "https://api.resend.com/emails"

#: A bearer credential wherever a line of text quotes one - by position, so a
#: key that is not the configured one (a stale deploy, a pasted typo) is caught
#: too.
_BEARER = re.compile(r"(Bearer\s+)\S+", re.IGNORECASE)

#: Tests put an httpx.MockTransport here; None is the real network.
_transport: httpx.AsyncBaseTransport | None = None


def redact(text: str) -> str:
    """`text` with the Resend API key taken out."""
    text = _BEARER.sub(r"\1<redacted>", text)
    key = settings.resend_api_key.get_secret_value()
    return text.replace(key, "<redacted>") if key else text


outbound.register_redactor(redact)


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    html: str
    text: str
    #: The same key for every attempt at the same message: a retry after a
    #: timeout the provider had in fact accepted is then not a second email.
    idempotency_key: str


class EmailSender(Protocol):
    async def send(self, email: Email) -> str | None:
        """Send `email`. None on success, else why not, without the credential."""
        ...


class ResendSender:
    """Resend's HTTP API. The sender address must be on a domain verified there."""

    async def send(self, email: Email) -> str | None:
        return await outbound.post_with_retries(
            RESEND_URL,
            json={
                "from": settings.email_from.strip(),
                "to": [email.to],
                "subject": email.subject,
                "html": email.html,
                "text": email.text,
            },
            headers={
                "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
                # Resend keeps a key for 24 hours and answers a repeat with the
                # first send's result instead of sending again.
                "Idempotency-Key": email.idempotency_key,
            },
            transport=_transport,
            # Resend's own reason, e.g. "The voltbox.ge domain is not verified".
            describe=lambda response: outbound.reason_from_body(response, "message"),
        )


def get_sender() -> EmailSender:
    return ResendSender()
