"""Phase 1 — სქემის ტესტები: ინვარიანტები, რომლებსაც ბაზა უნდა იცავდეს."""

import uuid
from decimal import Decimal

import pytest
from app.db.models import Address, Brand, Category, Product, ProductImage, User
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


async def _category(db: AsyncSession, slug: str = "phones") -> Category:
    category = Category(
        slug=slug, name="ტელეფონები", filters=[{"key": "brand", "type": "checkbox"}]
    )
    db.add(category)
    await db.flush()
    return category


async def _brand(db: AsyncSession, name: str = "Samsung") -> Brand:
    brand = Brand(slug=name.lower(), name=name, country="სამხრეთ კორეა")
    db.add(brand)
    await db.flush()
    return brand


async def _user(db: AsyncSession, email: str = "user@example.com") -> User:
    user = User(email=email, password_hash="x", first_name="ნინო", last_name="კაპანაძე")
    db.add(user)
    await db.flush()
    return user


async def test_email_uniqueness_ignores_letter_case(db: AsyncSession) -> None:
    # CITEXT-ის გარეშე Giorgi@x.ge და giorgi@x.ge ორ ანგარიშად დარეგისტრირდებოდა
    await _user(db, "Giorgi@Example.GE")
    db.add(User(email="giorgi@example.ge", password_hash="y"))

    with pytest.raises(IntegrityError):
        await db.flush()


async def test_old_price_must_exceed_price(db: AsyncSession) -> None:
    category, brand = await _category(db), await _brand(db)
    db.add(
        Product(
            slug="bad-discount",
            name="X",
            category_id=category.id,
            brand_id=brand.id,
            price=Decimal("100.00"),
            old_price=Decimal("90.00"),
        )
    )

    with pytest.raises(IntegrityError):
        await db.flush()


async def test_stock_cannot_go_negative(db: AsyncSession) -> None:
    category, brand = await _category(db), await _brand(db)
    db.add(
        Product(
            slug="negative-stock",
            name="X",
            category_id=category.id,
            brand_id=brand.id,
            price=Decimal("10.00"),
            stock=-1,
        )
    )

    with pytest.raises(IntegrityError):
        await db.flush()


async def test_only_one_default_address_per_user(db: AsyncSession) -> None:
    user = await _user(db)
    db.add(Address(user_id=user.id, city="თბილისი", address_line="ა", is_default=True))
    await db.flush()
    db.add(Address(user_id=user.id, city="ბათუმი", address_line="ბ", is_default=True))

    with pytest.raises(IntegrityError):
        await db.flush()


async def test_only_one_primary_image_per_product(db: AsyncSession) -> None:
    category, brand = await _category(db), await _brand(db)
    product = Product(
        slug="p", name="X", category_id=category.id, brand_id=brand.id, price=Decimal("10.00")
    )
    db.add(product)
    await db.flush()
    db.add(ProductImage(product_id=product.id, url="/a.svg", is_primary=True))
    await db.flush()
    db.add(ProductImage(product_id=product.id, url="/b.svg", is_primary=True))

    with pytest.raises(IntegrityError):
        await db.flush()


async def test_category_filters_survive_a_round_trip(db: AsyncSession) -> None:
    # FilterSidebar მთლიანად ამ კონფიგზეა აგებული — jsonb-მა ის უცვლელად უნდა დააბრუნოს
    config = [
        {"key": "specs.network", "label": "5G", "type": "toggle", "match": "5G"},
        {"key": "specs.color", "label": "ფერი", "type": "swatch"},
    ]
    db.add(Category(slug="phones", name="ტელეფონები", filters=config))
    await db.flush()
    db.expunge_all()

    stored = await db.scalar(select(Category).where(Category.slug == "phones"))

    assert stored is not None
    assert stored.filters == config


async def test_product_defaults_match_frontend_constants(db: AsyncSession) -> None:
    category, brand = await _category(db), await _brand(db)
    product = Product(
        slug="defaults", name="X", category_id=category.id, brand_id=brand.id, price=Decimal("1.00")
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)

    # frontend-ის LOW_STOCK_THRESHOLD = 3
    assert product.low_stock_threshold == 3
    assert product.is_active is True
    assert product.is_new is False
    assert isinstance(product.id, uuid.UUID)
