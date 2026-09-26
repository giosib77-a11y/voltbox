"""The email that carries a password reset link.

What it does: builds one short message in Georgian - the link, how long it
works, what happens to the account's sessions, and what to do if the reader
never asked - as HTML and plain text, and sends it through `mailer`.
Where it fits: POST /auth/forgot-password schedules `send_link` as a background
task after the token is committed and after the response has gone out, so the
provider can neither fail the request nor change how long it takes. That is
half of what keeps a known address and an unknown one indistinguishable; the
other half is in `auth.issue_password_reset`.

Notes: the link is a credential until it is used or expires. It reaches the
provider in the message body, which httpx does not log. A failed send is one
ERROR line, through `outbound.redact` and then `scrub`, which takes the token
out wherever it appears - whole, or cut short after `token=` when a provider's
reason quotes the body and is truncated - and the recipient's address with it.

The token is in the URL's fragment, not its query. A browser never sends a
fragment to any server: not to the static host that serves the page, not in a
Referer, and not in the crash report the storefront posts, which carries the
path and query only.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from html import escape
from uuid import UUID

from app.core.config import settings
from app.core.security import PASSWORD_RESET_TTL
from app.services import mailer, outbound

logger = logging.getLogger("voltbox.email")

SHOP_NAME = "VoltBox"

SUBJECT = f"პაროლის აღდგენა — {SHOP_NAME}"

#: The storefront page that reads the token from the fragment.
RESET_PATH = "/reset-password"

#: A token after `token=`, whole or truncated. The alphabet is token_urlsafe's.
_TOKEN_AFTER_NAME = re.compile(r"(token=)[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class ResetLink:
    """Who gets the link, copied out before the request's session closes."""

    user_id: UUID
    recipient: str
    token: str


def link_url(token: str) -> str:
    return f"{settings.site_url.rstrip('/')}{RESET_PATH}#token={token}"


def _minutes() -> int:
    return int(PASSWORD_RESET_TTL.total_seconds() // 60)


def text_body(link: ResetLink) -> str:
    return "\n".join(
        [
            "გამარჯობა,",
            "",
            f"{SHOP_NAME}-ზე ამ ელფოსტის ანგარიშისთვის პაროლის აღდგენა მოითხოვეს.",
            "ახალი პაროლის დასაყენებლად გახსენით ბმული:",
            "",
            link_url(link.token),
            "",
            f"ბმული მოქმედებს {_minutes()} წუთი და მხოლოდ ერთხელ. თუ აღდგენა რამდენჯერმე",
            "მოითხოვეთ, იმუშავებს მხოლოდ ბოლო წერილის ბმული.",
            "ახალი პაროლის დაყენების შემდეგ ანგარიშიდან ყველა მოწყობილობაზე გამოხვალთ.",
            "",
            "თუ პაროლის აღდგენა არ მოგითხოვიათ, ეს წერილი უგულებელყავით — პაროლი არ შეიცვლება.",
            "",
            SHOP_NAME,
            "",
        ]
    )


def html_body(link: ResetLink) -> str:
    """Every value is escaped, as in order_email: one rule, no exceptions to track."""
    url = escape(link_url(link.token), quote=True)
    return (
        '<!doctype html><html lang="ka"><head><meta charset="utf-8">'
        f"<title>{escape(SUBJECT)}</title></head>"
        '<body style="margin:0;padding:24px;background:#f9fafb;'
        'font-family:Arial,Helvetica,sans-serif;color:#111827">'
        '<div style="max-width:560px;margin:0 auto;background:#ffffff;padding:24px">'
        '<h1 style="font-size:20px;margin:0 0 16px">პაროლის აღდგენა</h1>'
        f"<p>{escape(SHOP_NAME)}-ზე ამ ელფოსტის ანგარიშისთვის პაროლის აღდგენა მოითხოვეს. "
        "ახალი პაროლის დასაყენებლად გახსენით ბმული:</p>"
        f'<p><a href="{url}" style="display:inline-block;padding:10px 16px;'
        'background:#111827;color:#ffffff;text-decoration:none;border-radius:6px">'
        "ახალი პაროლის დაყენება</a></p>"
        f'<p style="font-size:13px;color:#4b5563;word-break:break-all">{url}</p>'
        f"<p>ბმული მოქმედებს {_minutes()} წუთი და მხოლოდ ერთხელ. თუ აღდგენა რამდენჯერმე "
        "მოითხოვეთ, იმუშავებს მხოლოდ ბოლო წერილის ბმული. ახალი პაროლის დაყენების შემდეგ "
        "ანგარიშიდან ყველა მოწყობილობაზე გამოხვალთ.</p>"
        '<p style="font-size:13px;color:#4b5563">თუ პაროლის აღდგენა არ მოგითხოვიათ, '
        "ეს წერილი უგულებელყავით — პაროლი არ შეიცვლება.</p>"
        "</div></body></html>"
    )


def scrub(text: str, link: ResetLink) -> str:
    """`text` without the token, in any length, and without the recipient."""
    text = text.replace(link.token, "<token>")
    text = _TOKEN_AFTER_NAME.sub(r"\1<token>", text)
    return text.replace(link.recipient, "<recipient>")


async def send_link(link: ResetLink) -> None:
    """Background task: email the link, and never raise."""
    if not settings.order_email_enabled:
        return

    # Its own key per message, unrelated to the token: a retry after a timeout
    # the provider had accepted is not a second email, and the provider never
    # holds anything derived from the token outside the body it delivers.
    idempotency_key = f"password-reset/{uuid.uuid4()}"

    async def send() -> str | None:
        # Built in here, inside attempt's catch: a body that failed to build
        # must not escape the background task either.
        email = mailer.Email(
            to=link.recipient,
            subject=SUBJECT,
            html=html_body(link),
            text=text_body(link),
            idempotency_key=idempotency_key,
        )
        return await mailer.get_sender().send(email)

    failure = await outbound.attempt(send)
    if failure is not None:
        # The account id finds the customer in the admin panel; the address and
        # the link stay out.
        logger.error(
            "Password reset email for account %s was not sent: %s",
            link.user_id,
            scrub(outbound.redact(failure), link),
        )
