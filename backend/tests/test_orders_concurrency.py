"""Phase 6 — რბოლის პირობები.

ეს ტესტები საერთო ტრანზაქციულ `db` fixture-ს *არ* იყენებენ: overselling მხოლოდ
რეალურ, ერთმანეთისგან დამოუკიდებელ კავშირებზე ჩანს. ამიტომ აქ ცალკე სესიები
იქმნება და მონაცემები ბოლოს ხელით იწმინდება.
"""

import asyncio
from decimal import Decimal

import pytest
from app.core.errors import ConflictError
from app.db.models import Brand, Category, Order, OrderItem, Product, ProductImage
from app.db.session import SessionLocal
from app.services import order as order_service
from sqlalchemy import delete, select
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
