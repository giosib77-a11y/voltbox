"""The ceiling on one product's total stock (A-072).

What it covers: `adjust_stock` refuses an increase that would take `products.stock`
past MAX_STOCK (1 000 000) with a 400 STOCK_LIMIT_EXCEEDED, writing nothing; the
ceiling itself is allowed; a decrease is never refused for it, so a row already
above it can be sold down; and an order cancellation's restock is held to it too.

Why it exists: products.stock is an int4 and one manual change is +-100 000, so
about 21 475 additions overflowed into a 500.
"""

import httpx
import pytest
from app.core.errors import ValidationError
from app.db.models import (
    REASON_MANUAL,
    REASON_ORDER_PLACED,
    REASON_RESTOCK,
    ROLE_ADMIN,
    InventoryMovement,
    Product,
)
from app.services import order as order_service
from app.services import order_status
from app.services.inventory import MAX_STOCK, adjust_stock
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

ADMIN = "/api/v1/admin"
CUSTOMER = {
    "first_name": "გიორგი",
    "last_name": "ბერიძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
}


async def _product(db: AsyncSession, *, stock: int) -> Product:
    category = await make_category(db, slug="ceiling")
    brand = await make_brand(db, "CeilingBrand")
    return await make_product(db, category, brand, slug="ceiling-1", stock=stock)


async def _stock(db: AsyncSession, product: Product) -> int:
    stock = await db.scalar(select(Product.stock).where(Product.id == product.id))
    assert stock is not None
    return stock


async def _movement_count(db: AsyncSession, product: Product) -> int:
    count = await db.scalar(
        select(func.count())
        .select_from(InventoryMovement)
        .where(InventoryMovement.product_id == product.id)
    )
    return int(count or 0)


def test_the_ceiling_is_one_million() -> None:
    assert MAX_STOCK == 1_000_000


async def test_an_increase_to_exactly_the_ceiling_is_accepted(db: AsyncSession) -> None:
    product = await _product(db, stock=MAX_STOCK - 5)

    new_stock = await adjust_stock(db, product.id, 5, REASON_RESTOCK)

    assert new_stock == MAX_STOCK
    assert await _stock(db, product) == MAX_STOCK
    assert await _movement_count(db, product) == 1


async def test_an_increase_one_past_the_ceiling_is_refused_and_writes_nothing(
    db: AsyncSession,
) -> None:
    product = await _product(db, stock=MAX_STOCK - 5)

    with pytest.raises(ValidationError) as caught:
        await adjust_stock(db, product.id, 6, REASON_RESTOCK)

    assert caught.value.code == "STOCK_LIMIT_EXCEEDED"
    assert caught.value.details == {
        "productId": str(product.id),
        "limit": MAX_STOCK,
        "current": MAX_STOCK - 5,
        "room": 5,
    }
    assert await _stock(db, product) == MAX_STOCK - 5
    assert await _movement_count(db, product) == 0


async def test_the_overflow_scenario_is_a_refusal_not_an_int4_overflow(db: AsyncSession) -> None:
    """Near 2^31 the old code reached Postgres and failed there as a 500."""
    product = await _product(db, stock=2_147_483_000)

    with pytest.raises(ValidationError) as caught:
        await adjust_stock(db, product.id, 100_000, REASON_RESTOCK)

    assert caught.value.code == "STOCK_LIMIT_EXCEEDED"
    assert caught.value.details["room"] == 0
    assert await _stock(db, product) == 2_147_483_000
    assert await _movement_count(db, product) == 0


async def test_a_decrease_from_above_the_ceiling_still_works(db: AsyncSession) -> None:
    """A row written before the limit existed must not become unsellable."""
    product = await _product(db, stock=MAX_STOCK + 500)

    new_stock = await adjust_stock(db, product.id, -100, REASON_MANUAL, note="count")

    assert new_stock == MAX_STOCK + 400
    assert await _stock(db, product) == MAX_STOCK + 400
    assert await _movement_count(db, product) == 1


async def test_an_increase_from_above_the_ceiling_is_refused(db: AsyncSession) -> None:
    product = await _product(db, stock=MAX_STOCK + 500)

    with pytest.raises(ValidationError) as caught:
        await adjust_stock(db, product.id, 1, REASON_RESTOCK)

    assert caught.value.code == "STOCK_LIMIT_EXCEEDED"
    assert caught.value.details["room"] == 0
    assert await _stock(db, product) == MAX_STOCK + 500


async def test_checkout_below_the_ceiling_is_unaffected(db: AsyncSession) -> None:
    product = await _product(db, stock=MAX_STOCK + 500)

    await order_service.create_order(
        db, items=[(product.id, 3)], customer=CUSTOMER, payment_method="cash", user=None
    )

    assert await _stock(db, product) == MAX_STOCK + 497


async def test_cancelling_an_order_is_held_to_the_ceiling_and_stays_whole(
    db: AsyncSession,
) -> None:
    """An admin restocked to within the order's size while it was open: the
    cancellation is refused, the order stays as it was and nothing is half-applied."""
    product = await _product(db, stock=10)
    order = await order_service.create_order(
        db, items=[(product.id, 4)], customer=CUSTOMER, payment_method="cash", user=None
    )
    await db.execute(update(Product).where(Product.id == product.id).values(stock=MAX_STOCK - 2))
    await db.flush()

    with pytest.raises(ValidationError) as caught:
        await order_status.transition(db, order.id, "cancelled", actor_id=None)

    assert caught.value.code == "STOCK_LIMIT_EXCEEDED"
    assert order.status == "pending"
    assert await _stock(db, product) == MAX_STOCK - 2
    reasons = [
        reason
        for (reason,) in await db.execute(
            select(InventoryMovement.reason).where(InventoryMovement.product_id == product.id)
        )
    ]
    assert reasons == [REASON_ORDER_PLACED]


@pytest.fixture
async def headers(db: AsyncSession) -> dict[str, str]:
    admin = await make_user(db, email="stock-ceiling-admin@voltbox.ge", role=ROLE_ADMIN)
    return auth_header(admin)


async def _adjust(
    client: httpx.AsyncClient, headers: dict[str, str], product: Product, change: int
) -> httpx.Response:
    return await client.post(
        f"{ADMIN}/inventory/{product.id}/adjust",
        headers=headers,
        json={"change": change, "reason": "restock"},
    )


async def test_the_admin_endpoint_accepts_an_adjustment_that_lands_on_the_ceiling(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    product = await _product(db, stock=MAX_STOCK - 100_000)

    response = await _adjust(client, headers, product, 100_000)

    assert response.status_code == 200
    assert response.json()["stock"] == MAX_STOCK


async def test_the_admin_endpoint_answers_400_one_past_the_ceiling(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    product = await _product(db, stock=MAX_STOCK - 99_999)

    response = await _adjust(client, headers, product, 100_000)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "STOCK_LIMIT_EXCEEDED"
    assert error["details"]["limit"] == MAX_STOCK
    assert error["details"]["room"] == 99_999
    assert await _stock(db, product) == MAX_STOCK - 99_999
    assert await _movement_count(db, product) == 0


async def test_repeated_maximum_adjustments_stop_at_the_ceiling(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    """The A-072 scenario in miniature: +100 000 again and again."""
    product = await _product(db, stock=0)

    statuses = [(await _adjust(client, headers, product, 100_000)).status_code for _ in range(11)]

    assert statuses == [200] * 10 + [400]
    assert await _stock(db, product) == MAX_STOCK


async def test_the_admin_endpoint_still_lets_a_decrease_through_above_the_ceiling(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    product = await _product(db, stock=MAX_STOCK + 500)

    response = await _adjust(client, headers, product, -100)

    assert response.status_code == 200
    assert response.json()["stock"] == MAX_STOCK + 400
