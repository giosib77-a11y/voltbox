"""Phase 6 — რბოლის პირობები.

ეს ტესტები საერთო ტრანზაქციულ `db` fixture-ს *არ* იყენებენ: overselling მხოლოდ
რეალურ, ერთმანეთისგან დამოუკიდებელ კავშირებზე ჩანს. ამიტომ აქ ცალკე სესიები
იქმნება და მონაცემები ბოლოს ხელით იწმინდება.
"""

import asyncio
import uuid
from decimal import Decimal

import pytest
from app.core.errors import ConflictError
from app.db.models import (
    REASON_ORDER_CANCELLED,
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
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

CUSTOMER = {
    "first_name": "გიორგი",
    "last_name": "ბერიძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
}


@pytest.fixture
async def last_unit() -> Product:
    """ერთი პროდუქტი, მარაგში ზუსტად 1 ცალით — ცალკე კავშირზე დაწერილი."""
    async with SessionLocal() as setup:
        category = Category(slug="race", name="race", filters=[])
        brand = Brand(slug="race-brand", name="RaceBrand")
        setup.add_all([category, brand])
        await setup.flush()
        product = Product(
            slug="the-last-one",
            name="The Last One",
            category_id=category.id,
            brand_id=brand.id,
            price=Decimal("50.00"),
            stock=1,
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
        await cleanup.execute(delete(OrderItem).where(OrderItem.product_id == product_id))
        await cleanup.execute(
            delete(Order).where(
                Order.id.in_(select(OrderItem.order_id).where(OrderItem.product_id == product_id))
            )
        )
        await cleanup.execute(delete(Order).where(Order.customer["city"].astext == "თბილისი"))
        await cleanup.execute(delete(ProductImage).where(ProductImage.product_id == product_id))
        await cleanup.execute(delete(Product).where(Product.id == product_id))
        await cleanup.execute(delete(Category).where(Category.slug == "race"))
        await cleanup.execute(delete(Brand).where(Brand.slug == "race-brand"))
        await cleanup.commit()


async def _try_order(product_id: object) -> str:
    """ერთი შეკვეთა საკუთარ კავშირზე. → "ok" ან "conflict"."""
    async with SessionLocal() as session:
        try:
            await order_service.create_order(
                session,
                items=[(product_id, 1)],  # type: ignore[list-item]
                customer=dict(CUSTOMER),
                payment_method="cash",
                user=None,
            )
            await session.commit()
        except ConflictError:
            await session.rollback()
            return "conflict"
        return "ok"


async def test_two_parallel_orders_for_the_last_unit(last_unit: Product) -> None:
    """ერთი უნდა გაიაროს, მეორემ 409 უნდა დააბრუნოს — მარაგი ვერ გახდება უარყოფითი."""
    results = await asyncio.gather(_try_order(last_unit.id), _try_order(last_unit.id))

    assert sorted(results) == ["conflict", "ok"]

    async with SessionLocal() as check:
        stock = await check.scalar(select(Product.stock).where(Product.id == last_unit.id))
    assert stock == 0


async def test_order_numbers_are_unique_under_concurrency(last_unit: Product) -> None:
    """ნომერი sequence-იდან მოდის — random()+retry დუბლიკატს დაუშვებდა."""
    async with SessionLocal() as session:
        numbers = {await order_service._next_order_number(session) for _ in range(50)}

    assert len(numbers) == 50


async def test_cancellation_restores_stock(last_unit: Product, db: AsyncSession) -> None:
    async with SessionLocal() as session:
        order = await order_service.create_order(
            session,
            items=[(last_unit.id, 1)],
            customer=dict(CUSTOMER),
            payment_method="cash",
            user=None,
        )
        await session.commit()
        order_id = order.id

    async with SessionLocal() as session:
        stored = await session.scalar(select(Order).where(Order.id == order_id))
        assert stored is not None
        await order_service.cancel(session, stored)
        await session.commit()

    async with SessionLocal() as check:
        stock = await check.scalar(select(Product.stock).where(Product.id == last_unit.id))
    assert stock == 1


async def _order_with_key(product_id: object, key: str, *, qty: int = 1) -> tuple[str, str]:
    """One checkout on its own connection. → (outcome, detail).

    Outcomes: ("ok", order_number) for a created or replayed order,
    ("conflict", code) for a refusal, ("error", type) for anything else - which
    is the case that used to happen and must not any more.
    """
    async with SessionLocal() as session:
        try:
            order = await order_service.create_order(
                session,
                items=[(product_id, qty)],  # type: ignore[list-item]
                customer=dict(CUSTOMER),
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
            # Deliberately broad, and it hides nothing: the caller asserts
            # that no outcome is "error", so anything caught here fails the
            # test by name instead of being swallowed.
            await session.rollback()
            return "error", type(exc).__name__
        return "ok", number


async def test_parallel_duplicates_of_one_key_make_one_order(last_unit: Product) -> None:
    """Five simultaneous submissions of the same checkout.

    Before the key was claimed up front, the losers of this race died on the
    unique index and the shopper saw a 500 for an order that had in fact gone
    through.
    """
    key = str(uuid.uuid4())
    results = await asyncio.gather(*(_order_with_key(last_unit.id, key) for _ in range(5)))

    outcomes = {outcome for outcome, _ in results}
    assert outcomes == {"ok"}, results

    numbers = {detail for _, detail in results}
    assert len(numbers) == 1, f"expected one order, got {numbers}"

    async with SessionLocal() as check:
        stock = await check.scalar(select(Product.stock).where(Product.id == last_unit.id))
        orders = await check.scalar(
            select(func.count()).select_from(Order).where(Order.idempotency_key == key)
        )
    # Charged exactly once, out of a stock of one.
    assert stock == 0
    assert orders == 1


async def test_the_last_unit_does_not_turn_a_duplicate_into_out_of_stock(
    last_unit: Product,
) -> None:
    """Two duplicates competing for the only unit both get the order.

    This is why the claim has to come before the stock check: the duplicate
    would otherwise reach the check while the original was still uncommitted,
    find nothing left, and tell the shopper the item sold out - to them, in
    between two clicks of their own.
    """
    key = str(uuid.uuid4())
    first, second = await asyncio.gather(
        _order_with_key(last_unit.id, key), _order_with_key(last_unit.id, key)
    )

    assert first[0] == "ok" and second[0] == "ok", (first, second)
    assert first[1] == second[1]


async def test_two_different_keys_still_compete_for_the_last_unit(last_unit: Product) -> None:
    """Idempotency must not become a way around the stock check.

    Two genuinely different checkouts are still two orders, and only one of
    them can have the last unit.
    """
    results = await asyncio.gather(
        _order_with_key(last_unit.id, str(uuid.uuid4())),
        _order_with_key(last_unit.id, str(uuid.uuid4())),
    )

    assert sorted(outcome for outcome, _ in results) == ["conflict", "ok"]
    conflicts = [detail for outcome, detail in results if outcome == "conflict"]
    assert conflicts == ["INSUFFICIENT_STOCK"]


async def _cancel(order_id: object) -> tuple[str, str]:
    """One cancellation on its own connection. → (outcome, detail)."""
    async with SessionLocal() as session:
        stored = await session.scalar(select(Order).where(Order.id == order_id))
        assert stored is not None
        try:
            await order_service.cancel(session, stored)
            await session.commit()
        except ConflictError as exc:
            await session.rollback()
            return "conflict", exc.code
        except Exception as exc:
            # Broad on purpose and hiding nothing: the caller asserts on the
            # outcomes, so anything caught here fails the test by name.
            await session.rollback()
            return "error", type(exc).__name__
        return "ok", "cancelled"


async def test_two_parallel_cancellations_restock_exactly_once(last_unit: Product) -> None:
    """Both readers used to see `pending` and both returned the stock.

    The item was ordered out of a stock of one, so a double restock is visible
    immediately: stock becomes 2 for a product only ever stocked with 1.
    """
    async with SessionLocal() as session:
        order = await order_service.create_order(
            session,
            items=[(last_unit.id, 1)],  # type: ignore[list-item]
            customer=dict(CUSTOMER),
            payment_method="cash",
            user=None,
        )
        await session.commit()
        order_id = order.id

    results = await asyncio.gather(_cancel(order_id), _cancel(order_id))

    assert sorted(outcome for outcome, _ in results) == ["conflict", "ok"], results
    refusals = [detail for outcome, detail in results if outcome == "conflict"]
    assert refusals == ["ORDER_NOT_CANCELLABLE"]

    async with SessionLocal() as check:
        stock = await check.scalar(select(Product.stock).where(Product.id == last_unit.id))
        movements = await check.scalar(
            select(func.count())
            .select_from(InventoryMovement)
            .where(
                InventoryMovement.order_id == order_id,
                InventoryMovement.reason == REASON_ORDER_CANCELLED,
            )
        )
    assert stock == 1, "the single unit came back once, not twice"
    assert movements == 1
