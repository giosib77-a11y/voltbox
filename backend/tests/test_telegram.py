"""The Telegram message the owner gets when an order is placed.

The real sender runs against an httpx.MockTransport, as the Supabase tests do
(95e94e7): every test here builds the real request, URL and all, and reads a
real response. The order does not depend on the message - it is committed
before the send is scheduled, and the send runs after the response.

The token sits in the URL path, and httpx writes that URL into its own INFO
log line and into its exceptions, so the log is checked on every path here -
success included, since that INFO line is written on success.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable, Generator
from typing import Any

import httpx
import pytest
from app.core.config import settings
from app.core.logging import JsonFormatter
from app.db.models import Order, Product
from app.main import app
from app.services import telegram
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_brand, make_category, make_product

TOKEN = "7412345678:AAH-sEcReTtOkEn_0123456789abcdefghij"
#: The part of the token that must never be printed. The bot id before the
#: colon is public - it is the bot's user id.
SECRET_PART = "sEcReTtOkEn_0123456789abcdefghij"
CHAT_ID = "-1001234567890"

CUSTOMER = {
    "firstName": "გიორგი",
    "lastName": "ბერიძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
    "comment": "",
}

Handler = Callable[[httpx.Request], Awaitable[httpx.Response]]


class FakeTelegram:
    """The Bot API's sendMessage, answering what the test tells it to."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.answer: Handler = self.ok

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return await self.answer(request)

    @staticmethod
    async def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})


def _status(code: int, description: str) -> Handler:
    async def answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            code, json={"ok": False, "error_code": code, "description": description}
        )

    return answer


def _raises(exc_type: type[httpx.TransportError], message: str = "") -> Handler:
    async def answer(request: httpx.Request) -> httpx.Response:
        raise exc_type(message.format(url=request.url), request=request)

    return answer


#: The ways a send fails, and how many attempts each is worth.
FAILURES: dict[str, tuple[Handler, int]] = {
    "unauthorized": (_status(401, "Unauthorized"), 1),
    "chat not found": (_status(400, "Bad Request: chat not found"), 1),
    "server error": (_status(502, "Bad Gateway"), 3),
    "timeout": (_raises(httpx.ConnectTimeout), 3),
    # A transport error whose text quotes the URL, as some do.
    "error naming the url": (_raises(httpx.ConnectError, "cannot reach {url}"), 3),
}


@pytest.fixture
def fake_telegram(monkeypatch: pytest.MonkeyPatch) -> FakeTelegram:
    fake = FakeTelegram()
    monkeypatch.setattr(telegram, "_transport", httpx.MockTransport(fake.handle))
    monkeypatch.setattr(telegram, "RETRY_DELAYS", (0.0, 0.0))
    monkeypatch.setattr(settings, "telegram_bot_token", SecretStr(TOKEN))
    monkeypatch.setattr(settings, "telegram_chat_id", CHAT_ID)
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
    category = await make_category(db, "phones")
    brand = await make_brand(db, "Samsung")
    one = await make_product(db, category, brand, slug="one", name="One", price="40.00", stock=5)
    two = await make_product(db, category, brand, slug="two", name="Two", price="99.99", stock=5)
    return one, two


def _checkout_body(products: tuple[Product, Product]) -> dict[str, Any]:
    one, two = products
    return {
        "items": [{"productId": str(one.id), "qty": 2}, {"productId": str(two.id), "qty": 1}],
        "customer": CUSTOMER,
        "paymentMethod": "cash",
    }


async def _place(
    client: httpx.AsyncClient, products: tuple[Product, Product], key: str | None = None
) -> httpx.Response:
    return await client.post(
        "/api/v1/orders",
        json=_checkout_body(products),
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )


def _telegram_records(records: list[logging.LogRecord]) -> list[logging.LogRecord]:
    return [r for r in records if r.name == "voltbox.telegram"]


class TestAPlacedOrder:
    async def test_is_sent_to_the_owner(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        fake_telegram: FakeTelegram,
        products: tuple[Product, Product],
    ) -> None:
        response = await _place(client, products)

        assert response.status_code == 201
        body = response.json()
        order = await db.scalar(select(Order).where(Order.order_number == body["orderNumber"]))
        assert order is not None

        [request] = fake_telegram.requests
        assert request.method == "POST"
        assert request.url.host == "api.telegram.org"
        assert request.url.path == f"/bot{TOKEN}/sendMessage"
        sent = json.loads(request.content)
        assert sent["chat_id"] == CHAT_ID
        assert sent["text"].splitlines() == [
            f"ახალი შეკვეთა {body['orderNumber']}",
            # 2 x 40.00 + 99.99; 50 or more, so delivery is free
            "პროდუქტები: 179.99 GEL",
            "მიწოდება: 0.00 GEL",
            "ჯამი: 179.99 GEL",
            "ნივთები: 3",
            f"{settings.site_url}/admin/orders/{order.id}",
        ]

    async def test_the_delivery_fee_is_its_own_line(
        self,
        client: httpx.AsyncClient,
        fake_telegram: FakeTelegram,
        products: tuple[Product, Product],
    ) -> None:
        """The owner reads what the courier collects, and what of it is delivery."""
        one, _ = products
        response = await client.post(
            "/api/v1/orders",
            json={
                **_checkout_body(products),
                "items": [{"productId": str(one.id), "qty": 1}],
            },
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        assert response.status_code == 201, response.text

        [request] = fake_telegram.requests
        lines = json.loads(request.content)["text"].splitlines()
        # 40.00 of goods to Tbilisi: below 50, so its 8.00 fee is charged.
        assert lines[1:4] == [
            "პროდუქტები: 40.00 GEL",
            "მიწოდება: 8.00 GEL",
            "ჯამი: 48.00 GEL",
        ]

    async def test_the_message_carries_no_customer_details(
        self,
        client: httpx.AsyncClient,
        fake_telegram: FakeTelegram,
        products: tuple[Product, Product],
    ) -> None:
        await _place(client, products)

        [request] = fake_telegram.requests
        text = json.loads(request.content)["text"]
        leaked = [value for value in CUSTOMER.values() if value and value in text]
        assert leaked == []

    async def test_a_replayed_checkout_is_not_sent_twice(
        self,
        client: httpx.AsyncClient,
        fake_telegram: FakeTelegram,
        products: tuple[Product, Product],
    ) -> None:
        key = str(uuid.uuid4())
        first = await _place(client, products, key)
        again = await _place(client, products, key)

        assert first.json()["orderNumber"] == again.json()["orderNumber"]
        assert len(fake_telegram.requests) == 1


class TestUnconfigured:
    @pytest.mark.parametrize(
        ("token", "chat_id"), [("", ""), (TOKEN, ""), ("", CHAT_ID)], ids=["both", "chat", "token"]
    )
    async def test_nothing_is_sent_and_nothing_logged_per_order(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: httpx.AsyncClient,
        fake_telegram: FakeTelegram,
        products: tuple[Product, Product],
        captured_logs: list[logging.LogRecord],
        token: str,
        chat_id: str,
    ) -> None:
        monkeypatch.setattr(settings, "telegram_bot_token", SecretStr(token))
        monkeypatch.setattr(settings, "telegram_chat_id", chat_id)

        response = await _place(client, products)

        assert response.status_code == 201
        assert fake_telegram.requests == []
        assert _telegram_records(captured_logs) == []

    def test_startup_says_so_once_and_not_as_an_error(
        self, monkeypatch: pytest.MonkeyPatch, captured_logs: list[logging.LogRecord]
    ) -> None:
        monkeypatch.setattr(settings, "telegram_bot_token", SecretStr(""))
        monkeypatch.setattr(settings, "telegram_chat_id", "")

        telegram.log_configuration()

        [record] = _telegram_records(captured_logs)
        assert record.levelno == logging.INFO
        assert "off" in record.getMessage()


class TestWhenTelegramFails:
    @pytest.mark.parametrize("failure", FAILURES)
    async def test_the_checkout_still_succeeds_and_the_failure_is_logged(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        fake_telegram: FakeTelegram,
        products: tuple[Product, Product],
        captured_logs: list[logging.LogRecord],
        failure: str,
    ) -> None:
        fake_telegram.answer, attempts = FAILURES[failure]

        response = await _place(client, products)

        assert response.status_code == 201
        number = response.json()["orderNumber"]
        assert await db.scalar(select(Order).where(Order.order_number == number)) is not None
        assert len(fake_telegram.requests) == attempts
        [record] = [r for r in _telegram_records(captured_logs) if r.levelno == logging.ERROR]
        assert number in record.getMessage()


class TestTheTokenIsInNoLog:
    @pytest.mark.parametrize("outcome", ["sent", *FAILURES])
    async def test_nor_in_the_response(
        self,
        client: httpx.AsyncClient,
        fake_telegram: FakeTelegram,
        products: tuple[Product, Product],
        captured_logs: list[logging.LogRecord],
        outcome: str,
    ) -> None:
        if outcome != "sent":
            fake_telegram.answer, _ = FAILURES[outcome]

        response = await _place(client, products)

        # Formatted the way production writes them, so the exception text and
        # the extra fields are checked along with the message.
        lines = [JsonFormatter().format(record) for record in captured_logs]
        assert [line for line in lines if SECRET_PART in line] == []
        assert SECRET_PART not in response.text
        # Not vacuous: the requests carried the token, and where httpx logged
        # the URL, the line is there with the token taken out.
        assert all(SECRET_PART in str(r.url) for r in fake_telegram.requests)
        if outcome in ("sent", "unauthorized", "chat not found", "server error"):
            assert any("api.telegram.org/bot<redacted>/sendMessage" in line for line in lines)
        if outcome != "sent":
            assert any('"level": "ERROR"' in line for line in lines)


async def test_the_response_is_sent_before_telegram_answers(
    client: httpx.AsyncClient,
    fake_telegram: FakeTelegram,
    products: tuple[Product, Product],
) -> None:
    """Straight ASGI, because the test client waits for background tasks and
    would hide the order in which the two happen. Telegram is held until the
    response has gone out; if the send ran first, the response never would."""
    release = asyncio.Event()

    async def held(request: httpx.Request) -> httpx.Response:
        await release.wait()
        return await FakeTelegram.ok(request)

    fake_telegram.answer = held
    body = json.dumps(_checkout_body(products)).encode()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/orders",
        "raw_path": b"/api/v1/orders",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"test"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"idempotency-key", str(uuid.uuid4()).encode()),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("test", 80),
    }
    requested = False

    async def receive() -> dict[str, Any]:
        nonlocal requested
        if not requested:
            requested = True
            return {"type": "http.request", "body": body, "more_body": False}
        await asyncio.Event().wait()  # the client never disconnects
        raise AssertionError("unreachable")

    responded = asyncio.Event()
    status: list[int] = []

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            status.append(message["status"])
        if message["type"] == "http.response.body" and not message.get("more_body"):
            responded.set()

    running = asyncio.create_task(app(scope, receive, send))  # type: ignore[arg-type]
    try:
        await asyncio.wait_for(responded.wait(), timeout=5)
        assert status == [201]
        assert not running.done()  # the send is still waiting on Telegram
    finally:
        release.set()
        await asyncio.wait_for(running, timeout=5)
    assert len(fake_telegram.requests) == 1
