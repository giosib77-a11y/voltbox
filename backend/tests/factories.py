"""ტესტების მონაცემთა ფაბრიკები.

ტესტები seed-ზე განზრახ არ ეყრდნობა: mock მონაცემები frontend-ში შეიძლება
შეიცვალოს და ტესტები უმიზეზოდ გატყდეს. აქ პატარა, დეტერმინისტული ნაკრებია.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.core.security import create_access_token, hash_password
from app.db.models import ROLE_CUSTOMER, Brand, Category, Product, ProductImage, User
from app.services.search import build_search_text
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
    short_description: str = "მოკლე აღწერა",
) -> Product:
    # search_text ჩაწერისას ივსება — ზუსტად ისე, როგორც seed-ში.
    # ფაბრიკაში დუბლირება განზრახია: ტესტები რეალურ write-გზას უნდა იმეორებდნენ,
    # თორემ ძებნა მხოლოდ ტესტებში „მუშაობდა“ ან პირიქით
    product = Product(
        slug=slug,
        name=name or slug,
        short_description=short_description,
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
        search_text=build_search_text(
            name=name or slug,
            brand_name=brand.name,
            category_name=category.name,
            category_slug=category.slug,
            short_description=short_description,
            tags=["tag"],
            specs=specs or {},
        ),
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


async def make_user(
    db: AsyncSession,
    *,
    email: str = "user@example.ge",
    role: str = ROLE_CUSTOMER,
    is_active: bool = True,
    password: str = "supersecret1",
) -> User:
    """A user with any role or active flag, without going through registration.

    Registration deliberately cannot produce an admin, and it is rate limited,
    so tests that need one build it here instead.
    """
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        first_name="ტესტ",
        last_name="მომხმარებელი",
        role=role,
        is_active=is_active,
    )
    db.add(user)
    await db.flush()
    return user


def auth_header(user: User) -> dict[str, str]:
    """Bearer header for a user, skipping the login round trip."""
    token, _ = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}
