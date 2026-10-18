"""A trashed order is hidden from customers, guests, the dashboard and admin customers.

What it covers (PROJECT.md -> Business Rules -> Order trash): a trashed order
is missing from the customer's own list and `GET /orders/{number}`, and the guest
lookup with the right token answers exactly what it answers for a number that
never existed; the dashboard's sales today, orders today, sales total, top
products and latest orders leave it out; the admin customers' order count, spend
and order list leave it out. Each of those comes back once `deleted_at` is
cleared again, so the filter is shown to be the only thing hiding the order.

The one place a trashed order must still be found is the idempotency replay of
`POST /orders`: the retry gets that order back, and no second order, stock
decrement or ledger row appears.

`deleted_at` is set directly on the row rather than through the trash route, so
these tests do not depend on how an order gets trashed. The hiding tests fail on
code without the filters (the order stays visible); the replay tests fail on
code that filters the idempotency lookup (a second order is placed).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from app.core.errors import ConflictError
from app.db.models import ROLE_ADMIN, InventoryMovement, Order, Product, User
from app.services import order as order_service
from app.services.order_status import transition
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

ADMIN = "/api/v1/admin"
UNKNOWN_NUMBER = "VB-20200101-00001"

#: The checkout body of the HTTP replay tests (camelCase, as the API takes it).
HTTP_CUSTOMER = {
    "firstName": "გიორგი",
    "lastName": "ბერიძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
    "comment": "",
}

#: What the service layer takes for an order placed in code.
SERVICE_CUSTOMER = {
    "first_name": "შემსყიდველი",
    "last_name": "ბერიძე",
    "phone": "555111222",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
}


@pytest.fixture
async def admin(db: AsyncSession) -> User:
    return await make_user(db, email="hidden-admin@voltbox.ge", role=ROLE_ADMIN)


@pytest.fixture
def admin_headers(admin: User) -> dict[str, str]:
    return auth_header(admin)


async def _product(db: AsyncSession, slug: str, *, price: str = "100.00") -> Product:
    category = await make_category(db, slug=f"cat-{slug}")
    brand = await make_brand(db, f"Brand-{slug}")
    return await make_product(db, category, brand, slug=slug, name=slug, price=price, stock=50)


async def _place(
    db: AsyncSession, product: Product, *, qty: int = 1, user: User | None = None
) -> Order:
    customer = (
        {**SERVICE_CUSTOMER, "email": "guest@example.ge"} if user is None else SERVICE_CUSTOMER
    )
    return await order_service.create_order(
        db, items=[(product.id, qty)], customer=dict(customer), payment_method="cash", user=user
    )


async def _deliver(db: AsyncSession, order: Order) -> None:
    for step in ("confirmed", "processing", "shipped", "delivered"):
        await transition(db, order.id, step, actor_id=None)


async def _set_trashed(db: AsyncSession, order: Order, trashed: bool) -> None:
    order.deleted_at = datetime.now(UTC) if trashed else None
    await db.flush()


async def _count(db: AsyncSession, model: type[Order] | type[InventoryMovement]) -> int:
    return int(await db.scalar(select(func.count()).select_from(model)) or 0)


# --- the customer's own orders ---------------------------------------------------------


async def test_a_trashed_order_is_missing_from_the_customers_list(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    customer = await make_user(db, email="own-list@example.ge")
    product = await _product(db, "own-list")
    kept = await _place(db, product, user=customer)
    gone = await _place(db, product, user=customer)
    headers = auth_header(customer)
    await _set_trashed(db, gone, True)

    listed = await client.get("/api/v1/orders", headers=headers)

    assert listed.status_code == 200
    assert [row["orderNumber"] for row in listed.json()] == [kept.order_number]

    await _set_trashed(db, gone, False)
    again = await client.get("/api/v1/orders", headers=headers)
    assert {row["orderNumber"] for row in again.json()} == {kept.order_number, gone.order_number}


async def test_a_trashed_order_is_404_order_not_found_for_its_owner(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    customer = await make_user(db, email="own-detail@example.ge")
    order = await _place(db, await _product(db, "own-detail"), user=customer)
    headers = auth_header(customer)
    assert (
        await client.get(f"/api/v1/orders/{order.order_number}", headers=headers)
    ).status_code == 200
    await _set_trashed(db, order, True)

    trashed = await client.get(f"/api/v1/orders/{order.order_number}", headers=headers)
    unknown = await client.get(f"/api/v1/orders/{UNKNOWN_NUMBER}", headers=headers)

    assert trashed.status_code == 404
    assert trashed.json()["error"]["code"] == "ORDER_NOT_FOUND"
    # The owner cannot tell "in the trash" from "never existed".
    assert trashed.content == unknown.content

    await _set_trashed(db, order, False)
    restored = await client.get(f"/api/v1/orders/{order.order_number}", headers=headers)
    assert restored.status_code == 200


# --- the guest lookup ------------------------------------------------------------------


async def test_a_trashed_guest_order_answers_the_lookup_like_an_unknown_number(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    order = await _place(db, await _product(db, "guest-lookup"))
    token = order_service.issue_lookup_token(order)
    assert token is not None
    await db.flush()
    body = {"orderNumber": order.order_number, "token": token}
    assert (await client.post("/api/v1/orders/lookup", json=body)).status_code == 200
    await _set_trashed(db, order, True)

    trashed = await client.post("/api/v1/orders/lookup", json=body)
    unknown = await client.post(
        "/api/v1/orders/lookup", json={"orderNumber": UNKNOWN_NUMBER, "token": token}
    )

    assert trashed.status_code == unknown.status_code == 404
    assert trashed.json()["error"]["code"] == "ORDER_NOT_FOUND"
    # Same status, same content type, same bytes: code, message and details.
    assert trashed.headers["content-type"] == unknown.headers["content-type"]
    assert trashed.content == unknown.content

    await _set_trashed(db, order, False)
    assert (await client.post("/api/v1/orders/lookup", json=body)).status_code == 200


# --- the dashboard ---------------------------------------------------------------------


async def test_the_dashboard_leaves_out_a_trashed_delivered_order(
    client: httpx.AsyncClient, admin_headers: dict[str, str], db: AsyncSession
) -> None:
    kept_product = await _product(db, "dash-kept", price="60.00")
    gone_product = await _product(db, "dash-gone", price="400.00")
    kept = await _place(db, kept_product)
    gone = await _place(db, gone_product, qty=3)
    await _deliver(db, gone)
    assert gone.total == Decimal("1200.00")
    await _set_trashed(db, gone, True)

    hidden = (await client.get(f"{ADMIN}/dashboard", headers=admin_headers)).json()

    assert Decimal(hidden["salesToday"]) == kept.total
    assert hidden["ordersToday"] == 1
    assert Decimal(hidden["salesTotal"]) == kept.total
    assert [row["name"] for row in hidden["topProducts"]] == ["dash-kept"]
    assert [row["orderNumber"] for row in hidden["latestOrders"]] == [kept.order_number]

    await _set_trashed(db, gone, False)
    shown = (await client.get(f"{ADMIN}/dashboard", headers=admin_headers)).json()

    assert Decimal(shown["salesToday"]) == kept.total + gone.total
    assert shown["ordersToday"] == 2
    assert Decimal(shown["salesTotal"]) == kept.total + gone.total
    assert {row["name"] for row in shown["topProducts"]} == {"dash-kept", "dash-gone"}
    assert {row["orderNumber"] for row in shown["latestOrders"]} == {
        kept.order_number,
        gone.order_number,
    }


async def test_the_dashboard_of_a_shop_whose_only_order_is_trashed_is_empty(
    client: httpx.AsyncClient, admin_headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _place(db, await _product(db, "dash-only"))
    await _set_trashed(db, order, True)

    body = (await client.get(f"{ADMIN}/dashboard", headers=admin_headers)).json()

    assert Decimal(body["salesToday"]) == 0
    assert body["ordersToday"] == 0
    assert Decimal(body["salesTotal"]) == 0
    assert body["topProducts"] == []
    assert body["latestOrders"] == []


# --- the admin customers ---------------------------------------------------------------


async def test_admin_customers_leave_out_a_trashed_order(
    client: httpx.AsyncClient, admin_headers: dict[str, str], db: AsyncSession
) -> None:
    customer = await make_user(db, email="trash-spender@example.ge")
    product = await _product(db, "cust-trash", price="100.00")
    kept = await _place(db, product, qty=2, user=customer)
    gone = await _place(db, product, qty=1, user=customer)
    await _set_trashed(db, gone, True)
    url = f"{ADMIN}/customers/{customer.id}"

    listed = await client.get(
        f"{ADMIN}/customers", headers=admin_headers, params={"q": "trash-spender"}
    )
    detail = (await client.get(url, headers=admin_headers)).json()

    (row,) = listed.json()["items"]
    assert row["ordersCount"] == 1
    assert Decimal(row["totalSpent"]) == kept.total
    assert detail["ordersCount"] == 1
    assert Decimal(detail["totalSpent"]) == kept.total
    assert [order["orderNumber"] for order in detail["orders"]] == [kept.order_number]

    await _set_trashed(db, gone, False)
    listed = await client.get(
        f"{ADMIN}/customers", headers=admin_headers, params={"q": "trash-spender"}
    )
    detail = (await client.get(url, headers=admin_headers)).json()

    assert listed.json()["items"][0]["ordersCount"] == 2
    assert Decimal(listed.json()["items"][0]["totalSpent"]) == kept.total + gone.total
    assert detail["ordersCount"] == 2
    assert Decimal(detail["totalSpent"]) == kept.total + gone.total
    assert {order["orderNumber"] for order in detail["orders"]} == {
        kept.order_number,
        gone.order_number,
    }


# --- the idempotency replay ------------------------------------------------------------


async def _checkout(
    client: httpx.AsyncClient, product: Product, key: str, headers: dict[str, str] | None = None
) -> httpx.Response:
    return await client.post(
        "/api/v1/orders",
        json={
            "items": [{"productId": str(product.id), "qty": 2}],
            "customer": HTTP_CUSTOMER,
            "paymentMethod": "cash",
        },
        headers={"Idempotency-Key": key, **(headers or {})},
    )


@pytest.mark.parametrize("signed_in", [False, True], ids=["guest", "signed-in"])
async def test_a_replay_of_a_trashed_orders_checkout_returns_it_and_creates_nothing(
    client: httpx.AsyncClient, db: AsyncSession, signed_in: bool
) -> None:
    """A retry must never place a second order or take the stock a second time,
    even when the first order has since been moved to the trash. Both replay
    paths are unfiltered on purpose; the route builds the answer from the order
    the replay returned and never re-reads it through a getter that hides the
    trash."""
    product = await _product(db, f"replay-{'user' if signed_in else 'guest'}")
    headers = auth_header(await make_user(db, email="replayer@example.ge")) if signed_in else None
    key = str(uuid.uuid4())
    first = await _checkout(client, product, key, headers)
    assert first.status_code == 201, first.text
    order = await db.scalar(select(Order).where(Order.order_number == first.json()["orderNumber"]))
    assert order is not None
    await _set_trashed(db, order, True)
    orders = await _count(db, Order)
    movements = await _count(db, InventoryMovement)
    assert await db.scalar(select(Product.stock).where(Product.id == product.id)) == 48

    replay = await _checkout(client, product, key, headers)

    assert replay.status_code == 201, replay.text
    assert replay.json()["orderNumber"] == first.json()["orderNumber"]
    assert await _count(db, Order) == orders
    assert await _count(db, InventoryMovement) == movements
    assert await db.scalar(select(Product.stock).where(Product.id == product.id)) == 48
    # The replay did not bring the order out of the trash.
    await db.refresh(order)
    assert order.deleted_at is not None


# --- cancel ----------------------------------------------------------------------------


async def test_cancelling_a_trashed_order_reports_the_trash_not_a_closed_order(
    db: AsyncSession,
) -> None:
    product = await _product(db, "cancel-trash")
    order = await _place(db, product, qty=3)
    await _set_trashed(db, order, True)
    movements = await _count(db, InventoryMovement)

    with pytest.raises(ConflictError) as caught:
        await order_service.cancel(db, order)

    assert caught.value.code == "ORDER_IN_TRASH"
    assert await _count(db, InventoryMovement) == movements
    assert await db.scalar(select(Product.stock).where(Product.id == product.id)) == 47


async def test_cancelling_a_delivered_order_still_reports_it_can_no_longer_be_cancelled(
    db: AsyncSession,
) -> None:
    order = await _place(db, await _product(db, "cancel-delivered"))
    await _deliver(db, order)

    with pytest.raises(ConflictError) as caught:
        await order_service.cancel(db, order)

    assert caught.value.code == "ORDER_NOT_CANCELLABLE"
