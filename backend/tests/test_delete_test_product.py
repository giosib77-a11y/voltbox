"""scripts/delete_test_product.py: what it removes, and what it refuses to touch.

What it covers: the real path the --dry-run cannot show - the order that holds
the product, its items and the product's own ledger go, and every other
product's stock and ledger stay exactly as they were. Then each refusal: a
mistyped id, an order shared with another product, a category that is not
empty. A refusal leaves the database unchanged.
Notes: the Storage listing is replaced, so no test reaches the bucket.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.db.models import AdminAuditLog, Category, InventoryMovement, Order, OrderItem, Product
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import load_script, make_brand, make_category, make_product

SCRIPT = load_script("delete_test_product")


@pytest.fixture(autouse=True)
def _no_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SCRIPT, "_storage_keys_listed", lambda product_id: [])


async def _order(db: AsyncSession, number: str, *lines: tuple[Product, int]) -> Order:
    """An order for `lines`, with the stock movement each line writes at checkout."""
    total = sum(product.price * qty for product, qty in lines)
    order = Order(
        order_number=number,
        guest_phone="555000000",
        customer={"first_name": "ტესტი"},
        shipping_address={"city": "თბილისი"},
        subtotal=total,
        shipping=Decimal("0.00"),
        total=total,
    )
    db.add(order)
    await db.flush()
    for product, qty in lines:
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                product_slug=product.slug,
                unit_price=product.price,
                quantity=qty,
                line_total=product.price * qty,
            )
        )
        db.add(
            InventoryMovement(
                product_id=product.id,
                change=-qty,
                previous_stock=product.stock,
                new_stock=product.stock - qty,
                reason="order_placed",
                order_id=order.id,
            )
        )
        product.stock -= qty
    await db.flush()
    return order


async def _ledger(db: AsyncSession, product: Product) -> list[tuple[int, int, int]]:
    rows = await db.execute(
        select(
            InventoryMovement.change, InventoryMovement.previous_stock, InventoryMovement.new_stock
        )
        .where(InventoryMovement.product_id == product.id)
        .order_by(InventoryMovement.created_at, InventoryMovement.id)
    )
    return [tuple(row) for row in rows]


async def _count(db: AsyncSession, model, *where) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(*where))


async def _catalogue(db: AsyncSession):
    headphones = await make_category(db, "headphones")
    cables = await make_category(db, "cables")
    brand = await make_brand(db, "Apple")
    test = await make_product(db, headphones, brand, slug="iphone", name="Apple", images=0)
    other = await make_product(db, cables, brand, slug="usb-c", name="USB-C", images=0)
    return headphones, test, other


async def test_it_removes_the_order_the_product_and_its_ledger_only(db: AsyncSession) -> None:
    headphones, test, other = await _catalogue(db)
    await _order(db, "VB-1", (test, 1))
    await _order(db, "VB-2", (other, 2))
    other_ledger = await _ledger(db, other)
    other_stock = other.stock
    ids = {"test": test.id, "other": other.id, "category": headphones.id}

    plan = await SCRIPT.plan(db, test.id, "Apple", with_category=False)
    await SCRIPT.execute(db, plan, with_category=False)
    await db.flush()
    db.expire_all()

    assert await db.get(Product, ids["test"]) is None
    assert await _count(db, Order, Order.order_number == "VB-1") == 0
    assert await _count(db, OrderItem, OrderItem.product_id == ids["test"]) == 0
    assert await _count(db, InventoryMovement, InventoryMovement.product_id == ids["test"]) == 0
    assert await db.get(Category, ids["category"]) is not None, "kept without --with-category"

    # Everything about the other product is as it was
    remaining = await db.get(Product, ids["other"])
    assert remaining.stock == other_stock
    assert await _ledger(db, remaining) == other_ledger
    assert await _count(db, Order, Order.order_number == "VB-2") == 1

    actions = (
        await db.scalars(select(AdminAuditLog.action).order_by(AdminAuditLog.created_at))
    ).all()
    assert sorted(actions) == ["order.delete", "product.delete"]


async def test_with_category_it_removes_the_emptied_category(db: AsyncSession) -> None:
    headphones, test, _ = await _catalogue(db)
    category_id = headphones.id

    plan = await SCRIPT.plan(db, test.id, "Apple", with_category=True)
    await SCRIPT.execute(db, plan, with_category=True)
    await db.flush()
    db.expire_all()

    assert await db.get(Category, category_id) is None


async def test_it_refuses_an_order_shared_with_another_product(db: AsyncSession) -> None:
    _, test, other = await _catalogue(db)
    await _order(db, "VB-1", (test, 1), (other, 1))

    with pytest.raises(SCRIPT.RefusedError, match="VB-1 also contains 1 other"):
        await SCRIPT.plan(db, test.id, "Apple", with_category=False)


async def test_it_refuses_a_product_by_another_name(db: AsyncSession) -> None:
    _, test, _ = await _catalogue(db)

    with pytest.raises(SCRIPT.RefusedError, match="named 'Apple', not 'Samsung'"):
        await SCRIPT.plan(db, test.id, "Samsung", with_category=False)


async def test_it_refuses_a_category_that_is_not_empty(db: AsyncSession) -> None:
    headphones, test, other = await _catalogue(db)
    other.category_id = headphones.id
    await db.flush()

    with pytest.raises(SCRIPT.RefusedError, match="still has 1 other product"):
        await SCRIPT.plan(db, test.id, "Apple", with_category=True)
