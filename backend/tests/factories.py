"""ტესტების მონაცემთა ფაბრიკები.

ტესტები seed-ზე განზრახ არ ეყრდნობა: mock მონაცემები frontend-ში შეიძლება
შეიცვალოს და ტესტები უმიზეზოდ გატყდეს. აქ პატარა, დეტერმინისტული ნაკრებია.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.db.models import Brand, Category, Product, ProductImage
from sqlalchemy.ext.asyncio import AsyncSession

PHONES_FILTERS: list[dict[str, Any]] = [
    {"key": "brand", "label": "ბრენდი", "type": "checkbox"},
    {"key": "specs.ram", "label": "RAM", "type": "checkbox"},
    {"key": "specs.network", "label": "5G", "type": "toggle", "match": "5G"},
    {"key": "specs.color", "label": "ფერი", "type": "swatch"},
]


async def make_category(
    db: AsyncSession, slug: str = "phones", *, filters: list[dict[str, Any]] | None = None
) -> Category:
    category = Category(
        slug=slug,
        name=slug,
        short_name=slug,
        description="",
        icon="Smartphone",
        filters=filters if filters is not None else PHONES_FILTERS,
    )
    db.add(category)
    await db.flush()
    return category


async def make_brand(db: AsyncSession, name: str, country: str | None = "აშშ") -> Brand:
    brand = Brand(slug=name.lower(), name=name, country=country)
    db.add(brand)
    await db.flush()
    return brand


async def make_product(
    db: AsyncSession,
    category: Category,
    brand: Brand,
    *,
    slug: str,
    name: str | None = None,
    price: str = "1000.00",
    old_price: str | None = None,
    stock: int = 10,
    specs: dict[str, Any] | None = None,
    rating: str = "4.5",
    reviews_count: int = 10,
    is_new: bool = False,
    is_featured: bool = False,
    created_at: datetime | None = None,
    images: int = 3,
) -> Product:
    product = Product(
        slug=slug,
        name=name or slug,
        short_description="მოკლე აღწერა",
        description="სრული აღწერა",
        category_id=category.id,
        brand_id=brand.id,
        price=Decimal(price),
        old_price=Decimal(old_price) if old_price else None,
        stock=stock,
        specs=specs or {},
        tags=["tag"],
        rating=Decimal(rating),
        reviews_count=reviews_count,
        is_new=is_new,
        is_featured=is_featured,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=UTC),
    )
    db.add(product)
    await db.flush()
    for index in range(images):
        db.add(
            ProductImage(
                product_id=product.id,
                url=f"/images/{slug}-{index + 1}.svg",
                position=index,
                is_primary=index == 0,
            )
        )
    await db.flush()
    return product
