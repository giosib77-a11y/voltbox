"""The confirmation email a customer gets when their order is placed.

What it does: builds one message in Georgian - order number, each item with
its quantity and price, delivery fee, total, delivery address, payment method
and the shop's contacts - as HTML and as plain text, and sends it through
`mailer`.
Where it fits: the checkout route schedules `send_confirmation` as a
background task after the order has been committed, next to the owner's
Telegram notice, so the order never waits for the provider and never fails
because of it. A guest's address is the one typed at checkout; a signed-in
customer's is their account's.

Notes: product names come from the catalogue and the address from the
customer, so every value goes into the HTML through `escape`. The plain-text
part is not markup and takes them as they are. A failure is logged at ERROR
with the order number and without the recipient's address.

SHOP_CONTACT and PAYMENT_METHOD_LABELS are copies of what the storefront shows
(`frontend/src/constants/index.js`): the backend image does not carry the
frontend. tests/test_order_email.py fails when the two disagree.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from uuid import UUID

from app.core.config import settings
from app.services import mailer, outbound

logger = logging.getLogger("voltbox.email")

#: The footer's "კონტაქტი" column.
SHOP_CONTACT = {
    "phone": "+995 322 00 11 22",
    "email": "info@voltbox.ge",
    "address": "თბილისი, ჭავჭავაძის გამზირი 42",
    "workHours": "ორშ.–შაბ. 10:00–20:00",
}

SHOP_NAME = "VoltBox"

#: What the checkout calls each method.
PAYMENT_METHOD_LABELS = {
    "cash": "ნაღდი ანგარიშსწორება მიღებისას",
    "card_on_delivery": "ბარათით კურიერთან",
}


@dataclass(frozen=True)
class Line:
    name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class OrderConfirmation:
    """What the email says, copied out of the order before the session closes."""

    order_id: UUID
    order_number: str
    recipient: str
    lines: tuple[Line, ...]
    subtotal: Decimal
    shipping: Decimal
    total: Decimal
    currency: str
    city: str
    address: str
    payment_method: str


def log_configuration() -> None:
    """Say once, at startup, whether confirmations are on."""
    key = bool(settings.resend_api_key.get_secret_value())
    sender = bool(settings.email_from.strip())
    if key and sender:
        logger.info("Order confirmation emails are on")
    elif key or sender:
        # Half set is a mistake, not a choice.
        missing = "EMAIL_FROM" if key else "RESEND_API_KEY"
        logger.warning("Order confirmation emails are off: %s is not set", missing)
    else:
        logger.info("Order confirmation emails are off: RESEND_API_KEY and EMAIL_FROM are not set")


def _money(amount: Decimal, currency: str) -> str:
    return f"{amount:.2f} {'₾' if currency == 'GEL' else currency}"


def subject(order: OrderConfirmation) -> str:
    return f"შეკვეთა {order.order_number} მიღებულია — {SHOP_NAME}"


def _payment(order: OrderConfirmation) -> str:
    return PAYMENT_METHOD_LABELS.get(order.payment_method, order.payment_method)


def text_body(order: OrderConfirmation) -> str:
    currency = order.currency
    items = [
        f"- {line.name} — {line.quantity} × {_money(line.unit_price, currency)}"
        f" = {_money(line.line_total, currency)}"
        for line in order.lines
    ]
    return "\n".join(
        [
            "გმადლობთ შეკვეთისთვის!",
            "",
            f"შეკვეთის ნომერი: {order.order_number}",
            "",
            "პროდუქტები:",
            *items,
            "",
            f"პროდუქტები სულ: {_money(order.subtotal, currency)}",
            f"მიწოდება: {_money(order.shipping, currency)}",
            f"ჯამი: {_money(order.total, currency)}",
            "",
            f"მიწოდების მისამართი: {order.city}, {order.address}",
            f"გადახდის მეთოდი: {_payment(order)}",
            "",
            f"კითხვების შემთხვევაში დაგვიკავშირდით — {SHOP_NAME}:",
            f"ტელეფონი: {SHOP_CONTACT['phone']}",
            f"ელფოსტა: {SHOP_CONTACT['email']}",
            f"მისამართი: {SHOP_CONTACT['address']}",
            f"სამუშაო საათები: {SHOP_CONTACT['workHours']}",
            "",
        ]
    )


_CELL = 'style="padding:6px 8px;border-bottom:1px solid #e5e7eb"'
_RIGHT = 'style="padding:6px 8px;border-bottom:1px solid #e5e7eb;text-align:right"'


def _row(*cells: str) -> str:
    """A table row; the last cell is right-aligned. `cells` are already HTML."""
    *left, last = cells
    span = ' colspan="2"' if len(cells) == 2 else ""
    return (
        "<tr>"
        + "".join(f"<td {_CELL}{span}>{cell}</td>" for cell in left)
        + f"<td {_RIGHT}>{last}</td></tr>"
    )


def html_body(order: OrderConfirmation) -> str:
    """Every value is escaped, the shop's own included: one rule, no exceptions to track."""

    def money(amount: Decimal) -> str:
        return escape(_money(amount, order.currency))

    rows = "".join(
        _row(
            escape(line.name),
            f"{line.quantity} × {money(line.unit_price)}",
            money(line.line_total),
        )
        for line in order.lines
    )
    contact = SHOP_CONTACT
    return (
        '<!doctype html><html lang="ka"><head><meta charset="utf-8">'
        f"<title>{escape(subject(order))}</title></head>"
        '<body style="margin:0;padding:24px;background:#f9fafb;'
        'font-family:Arial,Helvetica,sans-serif;color:#111827">'
        '<div style="max-width:560px;margin:0 auto;background:#ffffff;padding:24px">'
        '<h1 style="font-size:20px;margin:0 0 16px">გმადლობთ შეკვეთისთვის!</h1>'
        f"<p>შეკვეთის ნომერი: <strong>{escape(order.order_number)}</strong></p>"
        '<table style="width:100%;border-collapse:collapse;font-size:14px">'
        f"{rows}"
        f"{_row('პროდუქტები სულ', money(order.subtotal))}"
        f"{_row('მიწოდება', money(order.shipping))}"
        f"{_row('<strong>ჯამი</strong>', f'<strong>{money(order.total)}</strong>')}"
        "</table>"
        f"<p>მიწოდების მისამართი: {escape(order.city)}, {escape(order.address)}</p>"
        f"<p>გადახდის მეთოდი: {escape(_payment(order))}</p>"
        '<hr style="border:0;border-top:1px solid #e5e7eb;margin:24px 0">'
        '<p style="font-size:13px;color:#4b5563">კითხვების შემთხვევაში დაგვიკავშირდით — '
        f"{escape(SHOP_NAME)}<br>"
        f"ტელეფონი: {escape(contact['phone'])}<br>"
        f"ელფოსტა: {escape(contact['email'])}<br>"
        f"მისამართი: {escape(contact['address'])}<br>"
        f"სამუშაო საათები: {escape(contact['workHours'])}</p>"
        "</div></body></html>"
    )


async def send_confirmation(order: OrderConfirmation) -> None:
    """Background task: email the customer, and never raise."""
    if not settings.order_email_enabled or not order.recipient:
        return

    async def send() -> str | None:
        # Built in here, inside send_quietly's catch: a body that failed to
        # build must not escape the background task either.
        email = mailer.Email(
            to=order.recipient,
            subject=subject(order),
            html=html_body(order),
            text=text_body(order),
            idempotency_key=f"order-confirmation/{order.order_id}",
        )
        return await mailer.get_sender().send(email)

    await outbound.send_quietly(
        send,
        logger=logger,
        what="Confirmation email",
        order_number=order.order_number,
        # A customer's address is not the log's business; the order number
        # finds it in the admin.
        scrub=lambda text: text.replace(order.recipient, "<recipient>"),
    )
