"""A repeated Idempotency-Key with a different cart is refused, not answered with the old order.

A-042: the same key and the same contact but qty 5 instead of 1 used to come
back as the qty-1 order under a 201, and the shopper believed they had ordered
five. `orders.request_hash` (migration 0017) is what tells a retry from a
different request.
"""

import asyncio
import re
import uuid
from collections.abc import AsyncGenerator, Mapping
from decimal import Decimal
from typing import Any

import httpx
import pytest
from app.core.errors import ConflictError
from app.db.models import (
    REASON_ORDER_PLACED,
    Brand,
    Category,
    InventoryMovement,
    Order,
    OrderItem,
    Product,
    ProductImage,
)
from app.db.session import SessionLocal
from app.services import order as order_service
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user
from tests.test_orders_concurrency import _until_queued_behind

KEY = "0d3c6a52-6b9a-4c57-9d55-2f1e8d7a4b01"

CUSTOMER = {
    "firstName": "გიორგი",
    "lastName": "ბერიძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
    "comment": "",
}


@pytest.fixture
async def shop(db: AsyncSession) -> dict[str, Product]:
    category = await make_category(db, "phones")
    brand = await make_brand(db, "Samsung")
    return {
        "cheap": await make_product(db, category, brand, slug="cheap", price="40.00", stock=10),
        "pricey": await make_product(db, category, brand, slug="pricey", price="200.00", stock=10),
    }


async def _place(
    client: httpx.AsyncClient,
    items: list[dict[str, object]],
    *,
    key: str = KEY,
    customer: Mapping[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return await client.post(
        "/api/v1/orders",
        json={"items": items, "customer": customer or CUSTOMER, "paymentMethod": "cash"},
        headers={"Idempotency-Key": key, **(headers or {})},
    )


def _line(product: Product, qty: int = 1) -> dict[str, object]:
    return {"productId": str(product.id), "qty": qty}


async def _orders_and_movements(db: AsyncSession) -> tuple[int, int]:
    orders = await db.scalar(select(func.count()).select_from(Order))
    movements = await db.scalar(
        select(func.count())
        .select_from(InventoryMovement)
        .where(InventoryMovement.reason == REASON_ORDER_PLACED)
    )
    return int(orders or 0), int(movements or 0)


async def test_the_same_request_under_the_same_key_replays_the_order(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    first = await _place(client, [_line(shop["cheap"])])
    second = await _place(client, [_line(shop["cheap"])])

    assert first.status_code == second.status_code == 201
    assert second.json()["orderNumber"] == first.json()["orderNumber"]
    assert await _orders_and_movements(db) == (1, 1)
    assert await db.scalar(select(Product.stock).where(Product.id == shop["cheap"].id)) == 9


async def test_the_same_key_with_a_different_quantity_is_refused(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """The A-042 scenario: qty 1, then qty 5 under one key and one contact."""
    first = await _place(client, [_line(shop["cheap"], 1)])
    assert first.status_code == 201

    second = await _place(client, [_line(shop["cheap"], 5)])

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert "orderNumber" not in second.json()
    # No second order, no second movement, and the stock is the qty-1 order's.
    assert await _orders_and_movements(db) == (1, 1)
    assert await db.scalar(select(Product.stock).where(Product.id == shop["cheap"].id)) == 9


@pytest.mark.parametrize(
    "change",
    ["other_product", "extra_line", "other_address", "other_comment", "other_name"],
)
async def test_any_other_change_to_the_request_is_refused_too(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product], change: str
) -> None:
    await _place(client, [_line(shop["cheap"])])
    items = [_line(shop["cheap"])]
    customer = dict(CUSTOMER)
    if change == "other_product":
        items = [_line(shop["pricey"])]
    elif change == "extra_line":
        items.append(_line(shop["pricey"]))
    elif change == "other_address":
        customer["address"] = "რუსთაველის გამზირი 1"
    elif change == "other_comment":
        customer["comment"] = "call first"
    else:
        customer["firstName"] = "ნიკა"

    response = await _place(client, items, customer=customer)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert await _orders_and_movements(db) == (1, 1)


async def test_a_signed_in_owner_with_a_different_cart_is_refused(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    user = await make_user(db, email="owner@voltbox.ge")
    headers = auth_header(user)
    await _place(client, [_line(shop["cheap"], 1)], headers=headers)

    response = await _place(client, [_line(shop["cheap"], 2)], headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert await _orders_and_movements(db) == (1, 1)


async def test_the_same_lines_in_another_order_are_the_same_request(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    first = await _place(client, [_line(shop["cheap"], 2), _line(shop["pricey"], 1)])
    second = await _place(client, [_line(shop["pricey"], 1), _line(shop["cheap"], 2)])

    assert second.status_code == 201
    assert second.json()["orderNumber"] == first.json()["orderNumber"]
    assert await _orders_and_movements(db) == (1, 2)


async def test_a_product_split_over_two_lines_is_the_merged_request(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    first = await _place(client, [_line(shop["cheap"], 2)])
    second = await _place(client, [_line(shop["cheap"], 1), _line(shop["cheap"], 1)])

    assert second.status_code == 201
    assert second.json()["orderNumber"] == first.json()["orderNumber"]


async def test_an_email_written_in_another_case_is_the_same_request(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    first = await _place(
        client, [_line(shop["cheap"])], customer=dict(CUSTOMER, email="Giorgi@Example.GE")
    )
    second = await _place(
        client, [_line(shop["cheap"])], customer=dict(CUSTOMER, email="  giorgi@example.ge ")
    )

    assert second.status_code == 201
    assert second.json()["orderNumber"] == first.json()["orderNumber"]


async def test_an_order_without_a_stored_hash_is_replayed_as_before(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """Placed before migration 0017: there is nothing to compare, so the key decides."""
    first = await _place(client, [_line(shop["cheap"], 1)])
    await db.execute(update(Order).values(request_hash=None))

    second = await _place(client, [_line(shop["cheap"], 5)])

    assert second.status_code == 201
    assert second.json()["orderNumber"] == first.json()["orderNumber"]
    assert await _orders_and_movements(db) == (1, 1)


async def test_a_stranger_with_a_different_request_learns_nothing(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """The owner check comes first: a different hash must not tell a non-owner anything."""
    await _place(client, [_line(shop["cheap"], 1)])
    stranger = dict(CUSTOMER, phone="599999999", firstName="ნინო")

    response = await _place(client, [_line(shop["cheap"], 5)], customer=stranger)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert "ბერიძე" not in response.text
    assert await _orders_and_movements(db) == (1, 1)


async def test_the_order_keeps_the_hash_of_its_request(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    response = await _place(client, [_line(shop["cheap"], 3)])

    stored = await db.scalar(
        select(Order.request_hash).where(Order.order_number == response.json()["orderNumber"])
    )
    assert stored is not None and re.fullmatch(r"[0-9a-f]{64}", stored)


def test_the_hash_ignores_line_order_and_splitting_but_not_content() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    customer: dict[str, Any] = {"first_name": "Ann", "phone": "555123456", "city": "თბილისი"}

    def digest(items: list[tuple[uuid.UUID, int]], **changes: Any) -> str:
        return order_service.request_hash(
            order_service._merge_lines(items),
            {**customer, **changes.pop("customer", {})},
            changes.pop("payment_method", "cash"),
        )

    base = digest([(a, 1), (b, 2)])
    assert digest([(b, 2), (a, 1)]) == base
    assert digest([(a, 1), (b, 1), (b, 1)]) == base
    assert digest([(a, 2), (b, 2)]) != base
    assert digest([(a, 1)]) != base
    assert digest([(a, 1), (b, 2)], payment_method="card_on_delivery") != base
    assert digest([(a, 1), (b, 2)], customer={"city": "ბათუმი"}) != base
    # Contact spellings the owner check already treats as one person.
    assert digest([(a, 1), (b, 2)], customer={"email": "A@B.GE"}) == digest(
        [(a, 1), (b, 2)], customer={"email": " a@b.ge "}
    )
    assert digest([(a, 1), (b, 2)], customer={"phone": "+995 555 123 456"}) == base
    # No email and an absent one are the same request.
    assert digest([(a, 1), (b, 2)], customer={"email": None}) == base


async def test_request_hash_is_a_nullable_64_character_column_with_no_default(
    db: AsyncSession,
) -> None:
    row = (
        await db.execute(
            text(
                """
                select data_type, character_maximum_length, is_nullable, column_default
                from information_schema.columns
                where table_schema = 'public' and table_name = 'orders'
                  and column_name = 'request_hash'
                """
            )
        )
    ).one()

    assert row.data_type == "character varying"
    assert row.character_maximum_length == 64
    # NULL is what an order from before the migration holds.
    assert row.is_nullable == "YES"
    assert row.column_default is None


@pytest.fixture
async def stocked() -> AsyncGenerator[Product]:
    """A product with stock 10, written on its own connection (as the race tests do)."""
    async with SessionLocal() as setup:
        category = Category(slug="hash-race", name="hash-race", filters=[])
        brand = Brand(slug="hash-race-brand", name="HashRaceBrand")
        setup.add_all([category, brand])
        await setup.flush()
        product = Product(
            slug="hash-race-product",
            name="Hash Race",
            category_id=category.id,
            brand_id=brand.id,
            price=Decimal("50.00"),
            stock=10,
        )
        setup.add(product)
        await setup.flush()
        setup.add(ProductImage(product_id=product.id, url="/a.svg", is_primary=True))
        await setup.commit()
        product_id = product.id

    async with SessionLocal() as session:
        loaded = await session.scalar(select(Product).where(Product.id == product_id))
        assert loaded is not None
        yield loaded

    async with SessionLocal() as cleanup:
        mine = select(OrderItem.order_id).where(OrderItem.product_id == product_id)
        await cleanup.execute(delete(Order).where(Order.id.in_(mine)))
        await cleanup.execute(delete(ProductImage).where(ProductImage.product_id == product_id))
        await cleanup.execute(delete(Product).where(Product.id == product_id))
        await cleanup.execute(delete(Category).where(Category.slug == "hash-race"))
        await cleanup.execute(delete(Brand).where(Brand.slug == "hash-race-brand"))
        await cleanup.commit()


_RACE_CUSTOMER = {
    "first_name": "გიორგი",
    "last_name": "ბერიძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
}


async def _second_checkout(product_id: uuid.UUID, key: str, qty: int) -> tuple[str, str]:
    async with SessionLocal() as session:
        try:
            order = await order_service.create_order(
                session,
                items=[(product_id, qty)],
                customer=dict(_RACE_CUSTOMER),
                payment_method="cash",
                user=None,
                idempotency_key=key,
            )
            number = order.order_number
            await session.commit()
        except ConflictError as exc:
            await session.rollback()
            return "conflict", exc.code
        except Exception as exc:
            # Broad on purpose and hiding nothing: the test asserts on the outcome.
            await session.rollback()
            return "error", type(exc).__name__
        return "ok", number


@pytest.mark.parametrize(("qty", "outcome"), [(1, "replay"), (5, "refused")])
async def test_a_duplicate_that_loses_the_race_for_the_key_is_compared_too(
    stocked: Product, qty: int, outcome: str
) -> None:
    """The clash path: the pre-check cannot see the first request's uncommitted row.

    The second checkout passes the pre-check, queues on the unique index, and
    only on the violation reads what the first one wrote. It must compare the
    request there as well, or a different cart slips through whenever the two
    arrive in the same instant.
    """
    key = str(uuid.uuid4())
    async with SessionLocal() as first:
        placed = await order_service.create_order(
            first,
            items=[(stocked.id, 1)],
            customer=dict(_RACE_CUSTOMER),
            payment_method="cash",
            user=None,
            idempotency_key=key,
        )
        number = placed.order_number
        second = asyncio.create_task(_second_checkout(stocked.id, key, qty))
        await _until_queued_behind(first)
        await first.commit()
    answer = await second

    if outcome == "replay":
        assert answer == ("ok", number)
    else:
        assert answer == ("conflict", "IDEMPOTENCY_KEY_REUSED")
    async with SessionLocal() as check:
        orders = await check.scalar(
            select(func.count()).select_from(Order).where(Order.idempotency_key == key)
        )
        stock = await check.scalar(select(Product.stock).where(Product.id == stocked.id))
    assert orders == 1
    assert stock == 9
