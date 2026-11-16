"""პროდუქტების იმპორტი JSON-ფაილიდან.

ეს არის პროდუქტების დამატების *რეკომენდებული* გზა. Supabase-ის Table Editor-ით
ხელით შევსება სამი მიზეზით სახიფათოა:

  1. `category_id` და `brand_id` UUID-ებია — ხელით მოძებნა და ჩასმა შეცდომებს იწვევს
  2. `search_text` ავტომატურად არ ივსება — ძებნა ჩუმად ვერ იპოვის პროდუქტს
  3. სურათები ცალკე ცხრილშია, `is_primary` და `position` სწორად უნდა დაიწეროს

ეს სკრიპტი სამივეს თავად აგვარებს.

გაშვება:
    python scripts/import_products.py products.json
    python scripts/import_products.py products.json --dry-run     # მხოლოდ შემოწმება
    python scripts/import_products.py products.json --create-brands
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models import REASON_INITIAL, Brand, Category, Product, ProductImage
from app.db.session import SessionLocal, engine
from app.schemas.admin_product import MAX_LOW_STOCK_THRESHOLD
from app.services.inventory import MAX_STOCK, adjust_stock
from app.services.search import build_search_text

REQUIRED = ("slug", "name", "category", "brand", "price")
# Boolean fields of a row and the value a missing one takes.
FLAGS = {"isActive": True, "isFeatured": False, "isNew": False}
# products.reviews_count is an int4.
MAX_REVIEWS_COUNT = 2_147_483_647


class ProductImportError(Exception):
    """იმპორტის შეცდომა — ყოველთვის იმ პროდუქტის მითითებით, სადაც მოხდა."""


def slugify(value: str) -> str:
    ascii_only = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-") or value.lower()


def to_decimal(value: Any, field: str, slug: str) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProductImportError(f"{slug}: `{field}` არ არის რიცხვი: {value!r}") from exc


def to_int(value: Any, field: str, slug: str) -> int:
    """A whole number from the file, or a ProductImportError naming the field.

    Accepted: an int, an integral float (`5.0`) and a string of digits (`"5"`).
    Refused: `true`/`false` (a bool is an int in Python, so `int(True)` would
    silently import one unit - in a stock column that is a typo, not a number),
    a fraction (`1.5` would be truncated without a word), `null` and text.
    """
    if isinstance(value, bool):
        raise ProductImportError(f"{slug}: `{field}` არ არის მთელი რიცხვი: {value!r}")
    try:
        if isinstance(value, float):
            if not value.is_integer():
                raise ValueError(value)
            return int(value)
        if isinstance(value, (int, str)):
            return int(value)
    except ValueError as exc:
        raise ProductImportError(f"{slug}: `{field}` არ არის მთელი რიცხვი: {value!r}") from exc
    raise ProductImportError(f"{slug}: `{field}` არ არის მთელი რიცხვი: {value!r}")


def to_flag(value: Any, field: str, slug: str) -> bool:
    """A JSON `true`/`false`, or a ProductImportError naming the field.

    `bool("false")` is True, so a text, a number or `null` would silently turn a
    hidden product on (or a plain one into a featured one).
    """
    if not isinstance(value, bool):
        raise ProductImportError(f"{slug}: `{field}` უნდა იყოს true ან false: {value!r}")
    return value


def validate(row: dict[str, Any], index: int) -> None:
    slug = row.get("slug") or f"#{index}"
    for field in REQUIRED:
        if not row.get(field) and row.get(field) != 0:
            raise ProductImportError(f"{slug}: სავალდებულო ველი აკლია — `{field}`")

    price = to_decimal(row["price"], "price", slug)
    old_price = to_decimal(row.get("oldPrice"), "oldPrice", slug)
    if price is None or price < 0:
        raise ProductImportError(f"{slug}: `price` უარყოფითი ან ცარიელია")
    # ბაზაშიც არის CHECK, მაგრამ ცხადი შეტყობინება სჯობს IntegrityError-ს
    if old_price is not None and old_price <= price:
        raise ProductImportError(
            f"{slug}: `oldPrice` ({old_price}) უნდა იყოს `price`-ზე ({price}) მეტი"
        )
    # The import sets an absolute stock and writes the difference through
    # `adjust_stock`, which refuses an increase past MAX_STOCK. So the ceiling
    # here is MAX_STOCK, not MAX_STOCK_ADJUSTMENT: that one only caps the admin
    # form's initial stock and one manual change, `adjust_stock` does not apply
    # it, and an import is a bulk restock tool that can legitimately set a
    # larger number. Checked here so a dry-run says what a real run would do,
    # instead of the real run ending on a raw STOCK_LIMIT_EXCEEDED traceback.
    stock = to_int(row.get("stock", 0), "stock", slug)
    if not 0 <= stock <= MAX_STOCK:
        raise ProductImportError(f"{slug}: `stock` ({stock}) უნდა იყოს 0-დან {MAX_STOCK}-მდე")
    # products.low_stock_threshold is an int4; without the cap 3 000 000 000
    # passes the dry-run and fails at flush.
    threshold = to_int(row.get("lowStockThreshold", 3), "lowStockThreshold", slug)
    if not 0 <= threshold <= MAX_LOW_STOCK_THRESHOLD:
        raise ProductImportError(
            f"{slug}: `lowStockThreshold` ({threshold}) უნდა იყოს 0-დან "
            f"{MAX_LOW_STOCK_THRESHOLD}-მდე"
        )
    rating = to_decimal(row.get("rating", 0), "rating", slug) or Decimal("0")
    if not (0 <= rating <= 5):
        raise ProductImportError(f"{slug}: `rating` უნდა იყოს 0-დან 5-მდე")
    # products.reviews_count is an int4 and no API or admin schema caps it (the
    # admin cannot set it at all), so the column's own limit is the ceiling.
    reviews_count = to_int(row.get("reviewsCount", 0), "reviewsCount", slug)
    if not 0 <= reviews_count <= MAX_REVIEWS_COUNT:
        raise ProductImportError(
            f"{slug}: `reviewsCount` ({reviews_count}) უნდა იყოს 0-დან {MAX_REVIEWS_COUNT}-მდე"
        )
    for field, default in FLAGS.items():
        to_flag(row.get(field, default), field, slug)


async def resolve_category(db: AsyncSession, slug: str) -> Category:
    category = await db.scalar(select(Category).where(Category.slug == slug))
    if category is None:
        known = [c.slug for c in (await db.scalars(select(Category))).all()]
        raise ProductImportError(
            f"უცნობი კატეგორია `{slug}`. არსებულები: {', '.join(known) or '(არცერთი)'}"
        )
    return category


async def resolve_brand(db: AsyncSession, name: str, *, allow_create: bool) -> Brand:
    brand = await db.scalar(select(Brand).where(Brand.name == name))
    if brand is not None:
        return brand
    if not allow_create:
        known = [b.name for b in (await db.scalars(select(Brand))).all()]
        raise ProductImportError(
            f"უცნობი ბრენდი `{name}`. არსებულები: {', '.join(known) or '(არცერთი)'}. "
            f"ახლის შესაქმნელად დაამატე --create-brands"
        )
    brand = Brand(slug=slugify(name), name=name)
    db.add(brand)
    await db.flush()
    return brand


async def import_one(db: AsyncSession, row: dict[str, Any], *, allow_create_brands: bool) -> str:
    """→ "created" ან "updated". `slug` უნიკალური გასაღებია."""
    slug = str(row["slug"])
    category = await resolve_category(db, str(row["category"]))
    brand = await resolve_brand(db, str(row["brand"]), allow_create=allow_create_brands)

    product = await db.scalar(select(Product).options(lazyload("*")).where(Product.slug == slug))
    action = "updated" if product else "created"
    if product is None:
        product = Product(slug=slug)

    product.name = str(row["name"])
    product.sku = row.get("sku") or None
    product.short_description = str(row.get("shortDescription", ""))
    product.description = str(row.get("description", ""))
    product.category_id = category.id
    product.brand_id = brand.id
    product.price = to_decimal(row["price"], "price", slug) or Decimal("0")
    product.old_price = to_decimal(row.get("oldPrice"), "oldPrice", slug)
    product.low_stock_threshold = to_int(row.get("lowStockThreshold", 3), "lowStockThreshold", slug)
    product.specs = dict(row.get("specs", {}))
    product.tags = list(row.get("tags", []))
    product.rating = to_decimal(row.get("rating", 0), "rating", slug) or Decimal("0")
    product.reviews_count = to_int(row.get("reviewsCount", 0), "reviewsCount", slug)
    product.is_active = to_flag(row.get("isActive", FLAGS["isActive"]), "isActive", slug)
    product.is_featured = to_flag(row.get("isFeatured", FLAGS["isFeatured"]), "isFeatured", slug)
    product.is_new = to_flag(row.get("isNew", FLAGS["isNew"]), "isNew", slug)

    # ⚠️ ყველაზე მნიშვნელოვანი ნაბიჯი: ამის გარეშე პროდუქტი ბაზაში იქნება,
    # მაგრამ ძებნა მას ვერასდროს იპოვის
    product.search_text = build_search_text(
        name=product.name,
        # The file carries no English name, so an update keeps the one the admin
        # gave; a new product has none yet (None until the row is flushed).
        name_en=product.name_en or "",
        brand_name=brand.name,
        category_name=category.name,
        category_slug=category.slug,
        short_description=product.short_description,
        tags=product.tags,
        specs=product.specs,
    )

    db.add(product)
    await db.flush()

    # მარაგი ერთადერთი გზით — `adjust_stock`-ით, რომ ledger სრული იყოს.
    # სხვაობას ვწერთ და არა აბსოლუტურ მნიშვნელობას: ხელახლა იმპორტისას
    # კორექტირება ჩანაწერად აისახება და არა ჩუმ გადაწერად.
    desired = to_int(row.get("stock", 0), "stock", slug)
    delta = desired - product.stock
    if delta:
        await adjust_stock(db, product.id, delta, REASON_INITIAL)

    images = [str(url) for url in row.get("images", []) if url]
    if images:
        # სურათებს მთლიანად ვცვლით — რიგი და is_primary რომ არ აირიოს
        await db.execute(delete(ProductImage).where(ProductImage.product_id == product.id))
        for position, url in enumerate(images):
            db.add(
                ProductImage(
                    product_id=product.id,
                    url=url,
                    alt=product.name,
                    position=position,
                    is_primary=position == 0,
                )
            )
        await db.flush()

    return action


def load_rows(path: Path) -> list[dict[str, Any]]:
    """ფაილის წაკითხვა და ვალიდაცია — ბაზასთან შეხებამდე, სინქრონულად.

    ჯერ ყველა ჩანაწერს ვამოწმებთ და მხოლოდ მერე ვწერთ: ნახევრად შესრულებული
    იმპორტი ბაზას არათანმიმდევრულ მდგომარეობაში ტოვებდა.
    """
    if not path.exists():
        raise SystemExit(f"ფაილი ვერ მოიძებნა: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["products"] if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise SystemExit('ფაილი უნდა შეიცავდეს მასივს ან {"products": [...]}')

    for index, row in enumerate(rows, start=1):
        validate(row, index)
    print(f"  ✔ ვალიდაცია: {len(rows)} პროდუქტი")
    return rows


async def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        raise SystemExit("გამოყენება: python scripts/import_products.py products.json [--dry-run]")

    rows = load_rows(Path(args[0]))

    if "--dry-run" in flags:
        print("  --dry-run — ბაზაში არაფერი ჩაიწერა")
        await engine.dispose()
        return

    created = updated = 0
    async with SessionLocal() as db:
        for row in rows:
            if (
                await import_one(db, row, allow_create_brands="--create-brands" in flags)
                == "created"
            ):
                created += 1
            else:
                updated += 1
        await db.commit()

    await engine.dispose()
    print(f"  ✔ იმპორტი დასრულდა: {created} დაემატა, {updated} განახლდა")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ProductImportError as exc:
        raise SystemExit(f"  ✘ {exc}") from exc
