"""The confirmation email a customer gets when their order is placed.

The real sender - ResendSender, through outbound's retries - runs against an
httpx.MockTransport, as the Telegram and Supabase tests do (95e94e7): every
test here builds the real request, headers and all, and reads a real
response. The order does not depend on the email - it is committed before the
send is scheduled, and the send runs after the response.

The API key travels in the Authorization header, which httpx does not log;
the log is still checked on every path, with a provider error that quotes the
header back among them.
"""

import asyncio
import json
import logging
import re
import uuid
from collections.abc import Awaitable, Callable, Generator
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.core.config import settings
from app.core.logging import JsonFormatter
from app.db.models import Order, Product
from app.main import app
from app.services import mailer, order_email, outbound
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    auth_header,
    make_brand,
    make_category,
    make_product,
    make_user,
    respond_while_held,
)

API_KEY = "re_SeCrEtKeY_4f2a9c1e8b7d6a5f"
SENDER = "VoltBox <orders@voltbox.ge>"
GUEST_EMAIL = "nino@example.ge"

FRONTEND_CONSTANTS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "constants"

CUSTOMER = {
    "firstName": "ნინო",
    "lastName": "კაპანაძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
    "comment": "",
    "email": GUEST_EMAIL,
}

Handler = Callable[[httpx.Request], Awaitable[httpx.Response]]


class FakeResend:
    """Resend's POST /emails, answering what the test tells it to."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.answer: Handler = self.ok

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return await self.answer(request)

    @staticmethod
    async def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "49a3999c-0ce1-4ea6-ab68-afcd6dc2e794"})

    def sent(self) -> dict[str, Any]:
        [request] = self.requests
        body: dict[str, Any] = json.loads(request.content)
        return body


def _status(code: int, message: str) -> Handler:
    async def answer(request: httpx.Request) -> httpx.Response:
        text = message.format(
            to=json.loads(request.content)["to"][0],
            auth=request.headers.get("Authorization", ""),
        )
        return httpx.Response(code, json={"statusCode": code, "message": text, "name": "error"})

    return answer


def _raises(exc_type: type[httpx.TransportError]) -> Handler:
    async def answer(request: httpx.Request) -> httpx.Response:
        raise exc_type("", request=request)

    return answer


#: The ways a send fails, and how many attempts each is worth.
FAILURES: dict[str, tuple[Handler, int]] = {
    "invalid key": (_status(401, "API key is invalid"), 1),
    "domain not verified": (_status(403, "The voltbox.ge domain is not verified"), 1),
    # Resend names the address it refused; the log must not.
    "recipient refused": (_status(422, "Invalid `to` field: {to}"), 1),
    # A refusal that quotes the request's header back.
    "error quoting the key": (_status(400, "Bad header: Authorization: {auth}"), 1),
    "server error": (_status(500, "Internal server error"), 3),
    "timeout": (_raises(httpx.ConnectTimeout), 3),
}


@pytest.fixture
def fake_resend(monkeypatch: pytest.MonkeyPatch) -> FakeResend:
    fake = FakeResend()
    monkeypatch.setattr(mailer, "_transport", httpx.MockTransport(fake.handle))
    monkeypatch.setattr(outbound, "RETRY_DELAYS", (0.0, 0.0))
    monkeypatch.setattr(settings, "resend_api_key", SecretStr(API_KEY))
    monkeypatch.setattr(settings, "email_from", SENDER)
    # The owner's notice is not what these tests are about.
    monkeypatch.setattr(settings, "telegram_bot_token", SecretStr(""))
    return fake


@pytest.fixture
def captured_logs() -> Generator[list[logging.LogRecord]]:
    """Every record, from the root logger - not caplog, for the reason
    test_unhandled_errors.py gives."""
    records: list[logging.LogRecord] = []

    class Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Collector(level=logging.DEBUG)
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)


@pytest.fixture
async def products(db: AsyncSession) -> tuple[Product, Product]:
    category = await make_category(db, "cables")
    brand = await make_brand(db, "Anker")
    one = await make_product(db, category, brand, slug="one", name="One", price="40.00", stock=5)
    two = await make_product(db, category, brand, slug="two", name="Two", price="99.99", stock=5)
    return one, two


def _checkout_body(
    products: tuple[Product, ...], customer: dict[str, str] | None = None
) -> dict[str, Any]:
    items = [{"productId": str(products[0].id), "qty": 2}]
    items += [{"productId": str(p.id), "qty": 1} for p in products[1:]]
    return {"items": items, "customer": customer or CUSTOMER, "paymentMethod": "cash"}


async def _place(
    client: httpx.AsyncClient,
    products: tuple[Product, ...],
    *,
    customer: dict[str, str] | None = None,
    key: str | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return await client.post(
        "/api/v1/orders",
        json=_checkout_body(products, customer),
        headers={"Idempotency-Key": key or str(uuid.uuid4()), **(headers or {})},
    )


def _email_records(records: list[logging.LogRecord]) -> list[logging.LogRecord]:
    return [r for r in records if r.name == "voltbox.email"]


class TestAConfirmation:
    async def test_is_sent_to_a_guest_on_a_new_order(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        fake_resend: FakeResend,
        products: tuple[Product, Product],
    ) -> None:
        response = await _place(client, products)

        assert response.status_code == 201, response.text
        number = response.json()["orderNumber"]
        order = await db.scalar(select(Order).where(Order.order_number == number))
        assert order is not None
        assert order.guest_email == GUEST_EMAIL

        [request] = fake_resend.requests
        assert request.method == "POST"
        assert str(request.url) == "https://api.resend.com/emails"
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        assert request.headers["Idempotency-Key"] == f"order-confirmation/{order.id}"
        sent = fake_resend.sent()
        assert sent["from"] == SENDER
        assert sent["to"] == [GUEST_EMAIL]
        assert sent["subject"] == f"შეკვეთა {number} მიღებულია — VoltBox"
        lines = sent["text"].splitlines()
        # The items come in the order the order holds them, which is by
        # product id - random here - so they are compared as a set.
        assert sorted(lines[5:7]) == [
            "- One — 2 × 40.00 ₾ = 80.00 ₾",
            "- Two — 1 × 99.99 ₾ = 99.99 ₾",
        ]
        assert lines[:5] + lines[7:] == [
            "გმადლობთ შეკვეთისთვის!",
            "",
            f"შეკვეთის ნომერი: {number}",
            "",
            "პროდუქტები:",
            "",
            # 179.99 of goods: 50 or more, so delivery is free
            "პროდუქტები სულ: 179.99 ₾",
            "მიწოდება: 0.00 ₾",
            "ჯამი: 179.99 ₾",
            "",
            "მიწოდების მისამართი: თბილისი, ჭავჭავაძის გამზირი 42",
            "გადახდის მეთოდი: ნაღდი ანგარიშსწორება მიღებისას",
            "",
            "კითხვების შემთხვევაში დაგვიკავშირდით — VoltBox:",
            "ტელეფონი: +995 322 00 11 22",
            "ელფოსტა: info@voltbox.ge",
            "მისამართი: თბილისი, ჭავჭავაძის გამზირი 42",
            "სამუშაო საათები: ორშ.–შაბ. 10:00–20:00",
        ]
        html = sent["html"]
        for part in (number, "One", "2 × 40.00 ₾", "179.99 ₾", "ჭავჭავაძის გამზირი 42"):
            assert part in html, part

    async def test_the_delivery_fee_is_its_own_line(
        self,
        client: httpx.AsyncClient,
        fake_resend: FakeResend,
        products: tuple[Product, Product],
    ) -> None:
        one, _ = products
        response = await client.post(
            "/api/v1/orders",
            json={**_checkout_body(products), "items": [{"productId": str(one.id), "qty": 1}]},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert response.status_code == 201, response.text

        lines = fake_resend.sent()["text"].splitlines()
        # 40.00 of goods to Tbilisi: below 50, so its 8.00 fee is charged.
        assert lines[7:10] == ["პროდუქტები სულ: 40.00 ₾", "მიწოდება: 8.00 ₾", "ჯამი: 48.00 ₾"]

    async def test_goes_to_a_signed_in_customer_at_their_account_address(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        fake_resend: FakeResend,
        products: tuple[Product, Product],
    ) -> None:
        user = await make_user(db, email="account@example.ge")
        customer = {k: v for k, v in CUSTOMER.items() if k != "email"}

        response = await _place(client, products, customer=customer, headers=auth_header(user))

        assert response.status_code == 201, response.text
        assert fake_resend.sent()["to"] == ["account@example.ge"]

    async def test_a_replayed_checkout_is_not_sent_twice(
        self,
        client: httpx.AsyncClient,
        fake_resend: FakeResend,
        products: tuple[Product, Product],
    ) -> None:
        key = str(uuid.uuid4())
        first = await _place(client, products, key=key)
        again = await _place(client, products, key=key)

        assert first.json()["orderNumber"] == again.json()["orderNumber"]
        assert len(fake_resend.requests) == 1

    async def test_a_product_name_with_markup_arrives_escaped(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        fake_resend: FakeResend,
    ) -> None:
        """The catalogue's name and the customer's address, both as text."""
        category = await make_category(db, "cables")
        brand = await make_brand(db, "Anker")
        name = '<script>alert("x")</script> Cable & Co'
        product = await make_product(
            db, category, brand, slug="evil", name=name, price="60.00", stock=5
        )
        customer = {**CUSTOMER, "address": 'Rustaveli 1 <img src=x onerror="y">'}

        response = await _place(client, (product,), customer=customer)

        assert response.status_code == 201, response.text
        sent = fake_resend.sent()
        html = sent["html"]
        assert "<script>" not in html
        assert "<img" not in html
        assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; Cable &amp; Co" in html
        assert "Rustaveli 1 &lt;img src=x onerror=&quot;y&quot;&gt;" in html
        # Plain text is not markup: the name reads as the shop wrote it.
        assert f"- {name} — 2 × 60.00 ₾" in sent["text"]


class TestNotSent:
    @pytest.mark.parametrize(
        ("key", "sender"), [("", ""), (API_KEY, ""), ("", SENDER)], ids=["both", "sender", "key"]
    )
    async def test_when_unconfigured_nothing_is_sent_or_logged_per_order(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: httpx.AsyncClient,
        fake_resend: FakeResend,
        products: tuple[Product, Product],
        captured_logs: list[logging.LogRecord],
        key: str,
        sender: str,
    ) -> None:
        monkeypatch.setattr(settings, "resend_api_key", SecretStr(key))
        monkeypatch.setattr(settings, "email_from", sender)

        response = await _place(client, products)

        assert response.status_code == 201
        assert fake_resend.requests == []
        assert _email_records(captured_logs) == []

    @pytest.mark.parametrize(
        ("key", "sender", "level", "names"),
        [
            ("", "", logging.INFO, "RESEND_API_KEY and EMAIL_FROM"),
            (API_KEY, "", logging.WARNING, "EMAIL_FROM"),
            ("", SENDER, logging.WARNING, "RESEND_API_KEY"),
        ],
        ids=["both", "sender", "key"],
    )
    def test_startup_says_it_is_off_once(
        self,
        monkeypatch: pytest.MonkeyPatch,
        captured_logs: list[logging.LogRecord],
        key: str,
        sender: str,
        level: int,
        names: str,
    ) -> None:
        monkeypatch.setattr(settings, "resend_api_key", SecretStr(key))
        monkeypatch.setattr(settings, "email_from", sender)

        order_email.log_configuration()

        [record] = _email_records(captured_logs)
        assert record.levelno == level
        assert "off" in record.getMessage()
        assert names in record.getMessage()

    async def test_a_guest_who_gave_no_address_is_skipped_silently(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        fake_resend: FakeResend,
        products: tuple[Product, Product],
        captured_logs: list[logging.LogRecord],
    ) -> None:
        customer = {k: v for k, v in CUSTOMER.items() if k != "email"}

        response = await _place(client, products, customer=customer)

        assert response.status_code == 201
        assert fake_resend.requests == []
        assert _email_records(captured_logs) == []


class TestWhenTheProviderFails:
    @pytest.mark.parametrize("failure", FAILURES)
    async def test_the_checkout_still_succeeds_and_the_failure_is_logged(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        fake_resend: FakeResend,
        products: tuple[Product, Product],
        captured_logs: list[logging.LogRecord],
        failure: str,
    ) -> None:
        fake_resend.answer, attempts = FAILURES[failure]

        response = await _place(client, products)

        assert response.status_code == 201
        number = response.json()["orderNumber"]
        assert await db.scalar(select(Order).where(Order.order_number == number)) is not None
        assert len(fake_resend.requests) == attempts
        # One key for every attempt: a retry is the same email, not another.
        assert len({r.headers["Idempotency-Key"] for r in fake_resend.requests}) == 1
        [record] = [r for r in _email_records(captured_logs) if r.levelno == logging.ERROR]
        assert number in record.getMessage()
        assert GUEST_EMAIL not in record.getMessage()


class TestTheKeyIsInNoLog:
    @pytest.mark.parametrize("outcome", ["sent", *FAILURES])
    async def test_nor_in_the_response(
        self,
        client: httpx.AsyncClient,
        fake_resend: FakeResend,
        products: tuple[Product, Product],
        captured_logs: list[logging.LogRecord],
        outcome: str,
    ) -> None:
        if outcome != "sent":
            fake_resend.answer, _ = FAILURES[outcome]

        response = await _place(client, products)

        # Formatted the way production writes them, so the exception text and
        # the extra fields are checked along with the message.
        lines = [JsonFormatter().format(record) for record in captured_logs]
        assert [line for line in lines if API_KEY in line] == []
        assert API_KEY not in response.text
        # Not vacuous: every request carried the key, and httpx logged them.
        assert all(API_KEY in r.headers["Authorization"] for r in fake_resend.requests)
        if outcome != "timeout":
            assert any("api.resend.com/emails" in line for line in lines)
        if outcome != "sent":
            assert any('"level": "ERROR"' in line for line in lines)


@pytest.mark.usefixtures("client")  # its database session serves the request
async def test_the_response_is_sent_before_the_provider_answers(
    fake_resend: FakeResend, products: tuple[Product, Product]
) -> None:
    """The provider is held until the response has gone out; if the send ran
    first, the response never would."""
    release = asyncio.Event()

    async def held(request: httpx.Request) -> httpx.Response:
        await release.wait()
        return await FakeResend.ok(request)

    fake_resend.answer = held

    status, still_sending = await respond_while_held(
        app, "/api/v1/orders", _checkout_body(products), release
    )

    assert status == 201
    assert still_sending  # the send was still waiting on the provider
    assert len(fake_resend.requests) == 1


class TestTheGuestEmailField:
    @pytest.mark.parametrize(
        "email", ["nino", "nino@", "@example.ge", "nino@example", "ni no@example.ge"]
    )
    async def test_a_malformed_address_is_refused(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        fake_resend: FakeResend,
        products: tuple[Product, Product],
        email: str,
    ) -> None:
        response = await _place(client, products, customer={**CUSTOMER, "email": email})

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert await db.scalar(select(Order)) is None
        assert fake_resend.requests == []

    async def test_an_emptied_field_is_no_address(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        fake_resend: FakeResend,
        products: tuple[Product, Product],
    ) -> None:
        response = await _place(client, products, customer={**CUSTOMER, "email": "  "})

        assert response.status_code == 201, response.text
        order = await db.scalar(select(Order))
        assert order is not None
        assert order.guest_email is None
        assert fake_resend.requests == []


def _frontend_object(name: str) -> str:
    source = (FRONTEND_CONSTANTS / "index.js").read_text(encoding="utf-8")
    start = source.index(f"export const {name}")
    return source[start : source.index("\n}", start)]


class TestTheEmailNamesThingsAsTheShopDoes:
    """The backend image does not carry the frontend, so the email keeps its
    own copies; these fail when a copy drifts from what the footer and the
    checkout show."""

    def test_the_contacts_are_the_footers(self) -> None:
        body = _frontend_object("CONTACT")
        footer = dict(re.findall(r"^\s{2}(\w+): '([^']*)'", body, re.M))

        assert footer, "CONTACT was not found in the frontend constants"
        for key, value in order_email.SHOP_CONTACT.items():
            assert footer.get(key) == value, key

    def test_the_payment_methods_are_named_as_at_checkout(self) -> None:
        source = (FRONTEND_CONSTANTS / "index.js").read_text(encoding="utf-8")
        start = source.index("export const PAYMENT_METHODS")
        body = source[start : source.index("\n];", start)]
        labels = dict(re.findall(r"value: '([a-z_]+)', label: '([^']*)'", body))

        assert labels, "PAYMENT_METHODS was not found in the frontend constants"
        assert labels == order_email.PAYMENT_METHOD_LABELS
