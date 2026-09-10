"""The stock ledger.

What it covers: that products.stock and inventory_movements never disagree -
checkout writes movements, cancelling gives the units back, stock cannot go
below zero, and only reasons an administrator is allowed to pick are accepted.

The ledger is only worth having if it is complete, so these tests assert on the
movement rows themselves and not merely on the resulting stock number.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import (
    REASON_CORRECTION,
    REASON_INITIAL,
    REASON_MANUAL,
    REASON_ORDER_CANCELLED,
    REASON_ORDER_PLACED,
    REASON_RESTOCK,
    InventoryMovement,
    Product,
)
from app.services import order as order_service
from app.services.inventory import adjust_stock, stock_status, validate_manual_adjustment
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_brand, make_category, make_product, make_user

CUSTOMER = {
    "first_name": "გიორგი",
    "last_name": "ბერიძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
}


async def _product(db: AsyncSession, *, stock: int = 10, slug: str = "widget") -> Product:
    category = await make_category(db, slug=f"cat-{slug}")
    brand = await make_brand(db, f"Brand-{slug}")
    return await make_product(db, category, brand, slug=slug, stock=stock)


async def _movements(db: AsyncSession, product_id: object) -> list[InventoryMovement]:
    stmt = (
        select(InventoryMovement)
        .where(InventoryMovement.product_id == product_id)
        .order_by(InventoryMovement.created_at, InventoryMovement.id)
    )
    return list((await db.scalars(stmt)).all())


async def test_adjust_stock_records_the_numbers_before_and_after(db: AsyncSession) -> None:
    product = await _product(db, stock=10)

    new_stock = await adjust_stock(db, product.id, 5, REASON_RESTOCK)

    assert new_stock == 15
    (movement,) = await _movements(db, product.id)
    assert (movement.previous_stock, movement.change, movement.new_stock) == (10, 5, 15)
    assert movement.reason == REASON_RESTOCK
    assert movement.created_by is None


async def test_adjust_stock_refuses_to_go_negative(db: AsyncSession) -> None:
    product = await _product(db, stock=3)

    with pytest.raises(ConflictError) as caught:
        await adjust_stock(db, product.id, -4, REASON_MANUAL)

    assert caught.value.code == "INSUFFICIENT_STOCK"
    assert caught.value.details["available"] == 3
    # Nothing was written: a refused adjustment must leave no trace.
    assert await _movements(db, product.id) == []
    assert await db.scalar(select(Product.stock).where(Product.id == product.id)) == 3


async def test_adjust_stock_rejects_a_zero_change(db: AsyncSession) -> None:
    product = await _product(db)

    with pytest.raises(ValidationError):
        await adjust_stock(db, product.id, 0, REASON_MANUAL)


async def test_adjust_stock_rejects_an_unknown_reason(db: AsyncSession) -> None:
    product = await _product(db)

    with pytest.raises(ValidationError):
        await adjust_stock(db, product.id, 1, "because-i-said-so")


async def test_adjust_stock_reports_a_missing_product(db: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await adjust_stock(db, uuid4(), 1, REASON_RESTOCK)


async def test_the_actor_is_recorded_for_a_manual_adjustment(db: AsyncSession) -> None:
    product = await _product(db, stock=4)
    admin = await make_user(db, email="stock-keeper@voltbox.ge")

    await adjust_stock(db, product.id, 6, REASON_RESTOCK, actor_id=admin.id, note="ახალი მიწოდება")

    (movement,) = await _movements(db, product.id)
    assert movement.created_by == admin.id
    assert movement.note == "ახალი მიწოდება"


async def test_checkout_writes_one_movement_per_item(db: AsyncSession) -> None:
    product = await _product(db, stock=10, slug="checkout-widget")

    order = await order_service.create_order(
        db, items=[(product.id, 3)], customer=CUSTOMER, payment_method="cash", user=None
    )

    (movement,) = await _movements(db, product.id)
    assert movement.reason == REASON_ORDER_PLACED
    assert (movement.previous_stock, movement.change, movement.new_stock) == (10, -3, 7)
    # The movement points back at the order that caused it.
    assert movement.order_id == order.id
    assert movement.created_by is None


async def test_cancelling_returns_the_units_and_records_it(db: AsyncSession) -> None:
    product = await _product(db, stock=10, slug="cancel-widget")
    order = await order_service.create_order(
        db, items=[(product.id, 4)], customer=CUSTOMER, payment_method="cash", user=None
    )
    assert await db.scalar(select(Product.stock).where(Product.id == product.id)) == 6

    await order_service.cancel(db, order)

    assert await db.scalar(select(Product.stock).where(Product.id == product.id)) == 10
    placed, cancelled = await _movements(db, product.id)
    assert placed.reason == REASON_ORDER_PLACED
    assert cancelled.reason == REASON_ORDER_CANCELLED
    assert (cancelled.previous_stock, cancelled.change, cancelled.new_stock) == (6, 4, 10)


async def test_cancelling_twice_does_not_restock_twice(db: AsyncSession) -> None:
    product = await _product(db, stock=10, slug="double-cancel")
    order = await order_service.create_order(
        db, items=[(product.id, 4)], customer=CUSTOMER, payment_method="cash", user=None
    )
    await order_service.cancel(db, order)

    with pytest.raises(ConflictError) as caught:
        await order_service.cancel(db, order)

    assert caught.value.code == "ORDER_NOT_CANCELLABLE"
    assert await db.scalar(select(Product.stock).where(Product.id == product.id)) == 10
    assert len(await _movements(db, product.id)) == 2


async def test_checkout_rejects_an_archived_product(db: AsyncSession) -> None:
    product = await _product(db, stock=10, slug="retired-widget")
    product.archived_at = datetime.now(UTC)
    product.is_active = False
    await db.flush()

    with pytest.raises(NotFoundError) as caught:
        await order_service.create_order(
            db, items=[(product.id, 1)], customer=CUSTOMER, payment_method="cash", user=None
        )

    assert caught.value.code == "PRODUCT_NOT_FOUND"
    assert await _movements(db, product.id) == []


async def test_checkout_rejects_an_inactive_product(db: AsyncSession) -> None:
    product = await _product(db, stock=10, slug="hidden-widget")
    product.is_active = False
    await db.flush()

    with pytest.raises(NotFoundError):
        await order_service.create_order(
            db, items=[(product.id, 1)], customer=CUSTOMER, payment_method="cash", user=None
        )


@pytest.mark.parametrize(
    ("reason", "note", "allowed"),
    [
        (REASON_RESTOCK, None, True),
        (REASON_MANUAL, "დათვლის შედეგი", True),
        (REASON_MANUAL, None, False),
        (REASON_MANUAL, "   ", False),
        (REASON_CORRECTION, None, False),
        # System reasons must never be selectable by hand: writing one would
        # claim an order caused a change that no order caused.
        (REASON_ORDER_PLACED, "მინდა", False),
        (REASON_INITIAL, "მინდა", False),
    ],
)
def test_manual_adjustment_rules(reason: str, note: str | None, allowed: bool) -> None:
    if allowed:
        validate_manual_adjustment(reason, note)
    else:
        with pytest.raises(ValidationError):
            validate_manual_adjustment(reason, note)


@pytest.mark.parametrize(
    ("stock", "threshold", "expected"),
    [(0, 3, "out"), (1, 3, "low"), (3, 3, "low"), (4, 3, "ok"), (0, 0, "out"), (1, 0, "ok")],
)
def test_stock_status(stock: int, threshold: int, expected: str) -> None:
    assert stock_status(stock, threshold) == expected


async def test_the_database_rejects_an_inconsistent_movement(db: AsyncSession) -> None:
    """The arithmetic check is enforced by Postgres, not only by Python.

    An application bug must not be able to write a row whose numbers do not add
    up, because such a row would silently poison every reconciliation later.
    """
    product = await _product(db, stock=10, slug="bad-math")
    db.add(
        InventoryMovement(
            product_id=product.id,
            change=5,
            previous_stock=10,
            new_stock=99,  # 10 + 5 != 99
            reason=REASON_RESTOCK,
        )
    )
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_a_multi_item_order_moves_every_line(db: AsyncSession) -> None:
    category = await make_category(db, slug="multi")
    brand = await make_brand(db, "MultiBrand")
    first = await make_product(db, category, brand, slug="m-1", price="10.00", stock=5)
    second = await make_product(db, category, brand, slug="m-2", price="2.50", stock=5)

    await order_service.create_order(
        db,
        items=[(first.id, 2), (second.id, 3)],
        customer=CUSTOMER,
        payment_method="cash",
        user=None,
    )

    assert await db.scalar(select(Product.stock).where(Product.id == first.id)) == 3
    assert await db.scalar(select(Product.stock).where(Product.id == second.id)) == 2
    assert len(await _movements(db, first.id)) == 1
    assert (await _movements(db, second.id))[0].change == -3


async def test_the_ledger_always_reconciles_with_stock(db: AsyncSession) -> None:
    """Sum of movements == current stock, after a realistic sequence."""
    product = await _product(db, stock=0, slug="reconcile")

    await adjust_stock(db, product.id, 20, REASON_INITIAL)
    await adjust_stock(db, product.id, 5, REASON_RESTOCK)
    order = await order_service.create_order(
        db, items=[(product.id, 7)], customer=CUSTOMER, payment_method="cash", user=None
    )
    await order_service.cancel(db, order)
    await adjust_stock(db, product.id, -2, REASON_CORRECTION, note="დაზიანებული")

    stock = await db.scalar(select(Product.stock).where(Product.id == product.id))
    ledger = sum(m.change for m in await _movements(db, product.id))
    assert stock == ledger == 23
