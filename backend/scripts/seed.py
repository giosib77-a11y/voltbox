"""საწყისი მონაცემების ჩატვირთვა frontend-ის mock წყაროდან.

ერთადერთი წყარო რჩება `src/data/*.js`. `export_mock_data.mjs` მას JSON-ად
გარდაქმნის, ეს სკრიპტი კი ბაზაში წერს. JSON არსად არ ინახება — ყოველ გაშვებაზე
თავიდან გენერირდება, რომ ორი წყარო ვერ დაშორდეს ერთმანეთს.

იდემპოტენტურია: ხელახლა გაშვება ჩანაწერებს ანახლებს და არ ადუბლირებს
(`slug` უნიკალურ გასაღებად გამოიყენება).

გაშვება:
    python scripts/seed.py
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models import Brand, Category, Product, ProductImage
from app.db.session import SessionLocal, engine
from app.services.search import build_search_text

BACKEND_DIR = Path(__file__).resolve().parents[1]
EXPORTER = BACKEND_DIR / "scripts" / "export_mock_data.mjs"


def load_mock_data() -> dict[str, list[dict[str, Any]]]:
    """Node-ს ვიძახებთ, რადგან წყარო ES-მოდულია და არა JSON."""
    try:
        result = subprocess.run(  # noqa: S603
            ["node", str(EXPORTER)],  # noqa: S607
            capture_output=True,
            cwd=BACKEND_DIR,
            check=True,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise SystemExit(
            "Node.js is required to read the frontend mock data. Install Node 18+ and retry."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Mock export failed:\n{exc.stderr.decode('utf-8', 'replace')}") from exc

    return json.loads(result.stdout.decode("utf-8"))


def slugify(value: str) -> str:
    """ლათინური slug — ქართული სახელებისთვის ტრანსლიტერაცია არ გვჭირდება,
    რადგან ბრენდები ლათინურია; ვამოწმებთ მხოლოდ უსაფრთხო სიმბოლოებს."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return slug or re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def upsert_categories(db: AsyncSession, rows: list[dict[str, Any]]) -> dict[str, Category]:
    existing = {c.slug: c for c in (await db.scalars(select(Category))).all()}
    result: dict[str, Category] = {}

    for position, row in enumerate(rows):
        slug = row["slug"]
        category = existing.get(slug) or Category(slug=slug)
        category.name = row["name"]
        category.short_name = row.get("shortName", row["name"])
        category.description = row.get("description", "")
        category.icon = row.get("icon", "Package")
        # ფილტრების კონფიგი უცვლელად გადადის — FilterSidebar მას პირდაპირ კითხულობს
        category.filters = row.get("filters", [])
        category.position = position
        db.add(category)
        # mock-ში კატეგორიის id სლაგის ტოლია (`phones`), პროდუქტები მასზე მიუთითებენ
        result[row["id"]] = category

    await db.flush()
    return result


async def upsert_brands(db: AsyncSession, rows: list[dict[str, Any]]) -> dict[str, Brand]:
    existing = {b.name: b for b in (await db.scalars(select(Brand))).all()}
    result: dict[str, Brand] = {}

    for row in rows:
        name = row["name"]
        brand = existing.get(name) or Brand(name=name)
        brand.slug = row.get("id") or slugify(name)
        brand.country = row.get("country")
        db.add(brand)
        result[name] = brand

    await db.flush()
    return result


async def upsert_products(
    db: AsyncSession,
    rows: list[dict[str, Any]],
    categories: dict[str, Category],
    brands: dict[str, Brand],
) -> tuple[int, int]:
    existing = {
        p.slug: p for p in (await db.scalars(select(Product).options(lazyload("*")))).unique().all()
    }
    created = updated = 0

    for row in rows:
        slug = row["slug"]
        product = existing.get(slug)
        if product is None:
            product = Product(slug=slug)
            created += 1
        else:
            updated += 1

        category = categories.get(row["category"])
        brand = brands.get(row["brand"])
        if category is None or brand is None:
            raise SystemExit(f"Unknown category/brand for product {slug!r}")

        product.sku = row["id"].upper()
        product.name = row["name"]
        product.short_description = row.get("shortDescription", "")
        product.description = row.get("description", "")
        product.category = category
        product.brand = brand
        product.price = to_decimal(row["price"]) or Decimal("0")
        product.old_price = to_decimal(row.get("oldPrice"))
        product.stock = int(row.get("stock", 0))
        product.specs = row.get("specs", {})
        product.tags = list(row.get("tags", []))
        product.rating = to_decimal(row.get("rating")) or Decimal("0")
        product.reviews_count = int(row.get("reviewsCount", 0))
        product.is_featured = bool(row.get("isFeatured"))
        product.is_new = bool(row.get("isNew"))
        product.is_active = True
        product.created_at = parse_iso(row["createdAt"])
        # საძებნი ტექსტი ჩაწერისას ივსება — query-ს დროს გამოთვლა ინდექსს გამორთავდა
        product.search_text = build_search_text(
            name=row["name"],
            brand_name=brand.name,
            category_name=category.name,
            category_slug=category.slug,
            short_description=row.get("shortDescription", ""),
            tags=list(row.get("tags", [])),
            specs=row.get("specs", {}),
        )
        db.add(product)
        await db.flush()

        # სურათებს ყოველ ჯერზე თავიდან ვწერთ — რიგი და is_primary რომ არ აირიოს.
        # bulk DELETE განზრახ: `product.images`-ზე მიმართვა lazy-load-ს იწვევდა და
        # async კონტექსტში MissingGreenlet-ით ვარდებოდა
        await db.execute(delete(ProductImage).where(ProductImage.product_id == product.id))

        for index, url in enumerate(row.get("images", [])):
            db.add(
                ProductImage(
                    product_id=product.id,
                    url=url,
                    alt=row["name"],
                    position=index,
                    is_primary=index == 0,
                )
            )

    await db.flush()
    return created, updated


async def main() -> None:
    data = load_mock_data()

    async with SessionLocal() as db:
        categories = await upsert_categories(db, data["categories"])
        brands = await upsert_brands(db, data["brands"])
        created, updated = await upsert_products(db, data["products"], categories, brands)
        await db.commit()

    await engine.dispose()
    print(
        f"seed complete: {len(categories)} categories, {len(brands)} brands, "
        f"{created} products created, {updated} updated"
    )


if __name__ == "__main__":
    asyncio.run(main())
