"""Product management for the admin panel.

What it does: the admin's filtered product listing, plus create, update,
archive, unarchive, duplicate and delete.
Where it fits: called by app/api/v1/routes/admin/products.py; shares slug
generation with categories and brands, and never writes stock itself - that
belongs to services/inventory.py.

Notes: every write path recomputes `search_text`. Skipping it is the failure
this codebase is most exposed to: the product appears in the catalogue and is
simply never found by search, with no error anywhere.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import REASON_INITIAL, Brand, Category, OrderItem, Product
from app.services import audit
from app.services.admin_image import discard_objects
from app.services.inventory import adjust_stock, stock_status
from app.services.search import build_search_text
from app.services.search_text import normalize
from app.services.slug import slugify, unique_slug
from app.services.storage import StorageBackend

#: Sorting is a whitelist, never a column name taken from the query string.
SORTABLE: dict[str, tuple[ColumnElement[Any], ...]] = {
    "created_desc": (Product.created_at.desc(),),
    "created_asc": (Product.created_at.asc(),),
    "name_asc": (Product.name.asc(),),
    "name_desc": (Product.name.desc(),),
    "price_asc": (Product.price.asc(),),
    "price_desc": (Product.price.desc(),),
    "stock_asc": (Product.stock.asc(),),
    "stock_desc": (Product.stock.desc(),),
}
DEFAULT_SORT = "created_desc"


async def _refresh_search_text(db: AsyncSession, product: Product) -> None:
    """Recompute products.search_text from the product and its relations.

    The value depends on the brand and category rows, which is why it cannot be
    a Postgres generated column and why every write path has to call this.
    """
    category = await db.get(Category, product.category_id)
    brand = await db.get(Brand, product.brand_id)
    product.search_text = build_search_text(
        name=product.name,
        brand_name=brand.name if brand else "",
        category_name=category.name if category else "",
        category_slug=category.slug if category else "",
        short_description=product.short_description,
        tags=list(product.tags or []),
        specs=dict(product.specs or {}),
    )


async def _assert_relations_exist(
    db: AsyncSession, category_id: uuid.UUID | None, brand_id: uuid.UUID | None
) -> None:
    if category_id is not None and await db.get(Category, category_id) is None:
        raise ValidationError(
            "Category does not exist",
            code="CATEGORY_NOT_FOUND",
            details=[{"field": "categoryId"}],
        )
    if brand_id is not None and await db.get(Brand, brand_id) is None:
        raise ValidationError(
            "Brand does not exist", code="BRAND_NOT_FOUND", details=[{"field": "brandId"}]
        )


def normalize_sku(value: str | None) -> str | None:
    """Uppercased and trimmed. `SKU-1` and `sku-1` are the same article."""
    if value is None:
        return None
    cleaned = value.strip().upper()
    return cleaned or None


async def _assert_sku_free(
    db: AsyncSession, sku: str | None, *, exclude_id: uuid.UUID | None = None
) -> None:
    if sku is None:
        return
    stmt = select(func.count()).select_from(Product).where(Product.sku == sku)
    if exclude_id is not None:
        stmt = stmt.where(Product.id != exclude_id)
    if await db.scalar(stmt):
        raise ConflictError(
            "This SKU is already used by another product",
            code="SKU_TAKEN",
            details=[{"field": "sku", "value": sku}],
        )


def _row_to_list_item(product: Product) -> dict[str, Any]:
    primary = next(
        (image.url for image in product.images if image.is_primary),
        next((image.url for image in sorted(product.images, key=lambda i: i.position)), None),
    )
    return {
        "id": product.id,
        "slug": product.slug,
        "sku": product.sku,
        "name": product.name,
        "category_name": product.category.name,
        "brand_name": product.brand.name,
        "price": product.price,
        "old_price": product.old_price,
        "stock": product.stock,
        "low_stock_threshold": product.low_stock_threshold,
        "stock_status": stock_status(product.stock, product.low_stock_threshold),
        "is_active": product.is_active,
        "is_featured": product.is_featured,
        "is_new": product.is_new,
        "archived_at": product.archived_at,
        "primary_image": primary,
        "created_at": product.created_at,
    }


def _filters(
    *,
    q: str | None,
    category_id: uuid.UUID | None,
    brand_id: uuid.UUID | None,
    is_active: bool | None,
    include_archived: bool,
    is_featured: bool | None,
    is_new: bool | None,
    low_stock: bool | None,
    price_min: Decimal | None,
    price_max: Decimal | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []

    # Archived products are hidden by default: they are retired, and an admin
    # looking at the catalogue should see what is live unless they ask.
    if not include_archived:
        conditions.append(Product.archived_at.is_(None))

    if q:
        needle = q.strip()
        if needle:
            # Three ways an admin looks for a product: by name (through the same
            # normalized search_text the storefront uses), by SKU, or by slug
            # pasted from a URL.
            normalized = normalize(needle)
            conditions.append(
                or_(
                    Product.search_text.ilike(f"%{normalized}%"),
                    Product.name.ilike(f"%{needle}%"),
                    Product.sku.ilike(f"{needle.upper()}%"),
                    Product.slug.ilike(f"%{needle.lower()}%"),
                )
            )

    if category_id is not None:
        conditions.append(Product.category_id == category_id)
    if brand_id is not None:
        conditions.append(Product.brand_id == brand_id)
    if is_active is not None:
        conditions.append(Product.is_active.is_(is_active))
    if is_featured is not None:
        conditions.append(Product.is_featured.is_(is_featured))
    if is_new is not None:
        conditions.append(Product.is_new.is_(is_new))
    if low_stock:
        conditions.append(Product.stock <= Product.low_stock_threshold)
    if price_min is not None:
        conditions.append(Product.price >= price_min)
    if price_max is not None:
        conditions.append(Product.price <= price_max)

    return conditions


async def list_products(
    db: AsyncSession,
    *,
    page: int,
    limit: int,
    sort: str = DEFAULT_SORT,
    **filters: Any,
) -> dict[str, Any]:
    """One page of the admin product table."""
    if sort not in SORTABLE:
        raise ValidationError(
            f"Unknown sort: {sort}", code="UNKNOWN_SORT", details={"allowed": sorted(SORTABLE)}
        )

    conditions = _filters(**filters)

    total = await db.scalar(select(func.count()).select_from(Product).where(*conditions))
    stmt = (
        select(Product)
        .options(selectinload(Product.images))
        .where(*conditions)
        .order_by(*SORTABLE[sort], Product.id)
        .limit(limit)
        .offset((page - 1) * limit)
    )
    products = (await db.scalars(stmt)).unique().all()

    total_count = int(total or 0)
    return {
        "items": [_row_to_list_item(product) for product in products],
        "total": total_count,
        "page": page,
        "total_pages": (total_count + limit - 1) // limit if limit else 0,
        "limit": limit,
    }


async def get_product(db: AsyncSession, product_id: uuid.UUID) -> dict[str, Any]:
    stmt = select(Product).options(selectinload(Product.images)).where(Product.id == product_id)
    product = (await db.scalars(stmt)).unique().one_or_none()
    if product is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")

    return {
        **{c.name: getattr(product, c.name) for c in Product.__table__.columns},
        "category_name": product.category.name,
        "brand_name": product.brand.name,
        "stock_status": stock_status(product.stock, product.low_stock_threshold),
        "images": sorted(product.images, key=lambda i: i.position),
    }


async def create_product(
    db: AsyncSession, payload: dict[str, Any], *, actor_id: uuid.UUID | None
) -> Product:
    await _assert_relations_exist(db, payload.get("category_id"), payload.get("brand_id"))

    sku = normalize_sku(payload.get("sku"))
    await _assert_sku_free(db, sku)

    slug = await _resolve_product_slug(db, explicit=payload.get("slug"), name=payload["name"])
    initial_stock = int(payload.pop("stock", 0) or 0)

    product = Product(
        slug=slug,
        sku=sku,
        name=payload["name"],
        short_description=payload.get("short_description") or "",
        description=payload.get("description") or "",
        category_id=payload["category_id"],
        brand_id=payload["brand_id"],
        price=payload["price"],
        old_price=payload.get("old_price"),
        stock=0,
        low_stock_threshold=payload.get("low_stock_threshold", 3),
        specs=payload.get("specs") or {},
        tags=payload.get("tags") or [],
        is_active=bool(payload.get("is_active", False)),
        is_featured=bool(payload.get("is_featured", False)),
        is_new=bool(payload.get("is_new", False)),
    )
    db.add(product)
    await db.flush()
    await _refresh_search_text(db, product)

    # Stock starts at zero and is moved into place through the ledger, so even a
    # product's opening balance has a movement explaining it.
    if initial_stock:
        await adjust_stock(db, product.id, initial_stock, REASON_INITIAL, actor_id=actor_id)

    await db.flush()
    return product


async def _resolve_product_slug(
    db: AsyncSession,
    *,
    explicit: str | None,
    name: str,
    exclude_id: uuid.UUID | None = None,
) -> str:
    if explicit:
        candidate = slugify(explicit)
        if not candidate:
            raise ValidationError("Slug contains no usable characters", code="INVALID_SLUG")
        stmt = select(func.count()).select_from(Product).where(Product.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(Product.id != exclude_id)
        if await db.scalar(stmt):
            raise ConflictError(
                "This slug is already taken",
                code="SLUG_TAKEN",
                details=[{"field": "slug", "value": candidate}],
            )
        return candidate

    return await unique_slug(
        db, Product.slug, slugify(name), exclude_id=exclude_id, id_column=Product.id
    )


async def update_product(
    db: AsyncSession, product_id: uuid.UUID, patch: dict[str, Any]
) -> tuple[Product, dict[str, Any], dict[str, Any]]:
    """Partial update. Returns the row plus before/after for auditing."""
    stmt = select(Product).options(selectinload(Product.images)).where(Product.id == product_id)
    product = (await db.scalars(stmt)).unique().one_or_none()
    if product is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")

    if product.archived_at is not None and patch.get("is_active") is True:
        # Reactivating something retired would put it back on the storefront
        # without anyone deciding to un-retire it.
        raise ConflictError("Unarchive the product before activating it", code="PRODUCT_ARCHIVED")

    await _assert_relations_exist(db, patch.get("category_id"), patch.get("brand_id"))

    if "sku" in patch:
        patch["sku"] = normalize_sku(patch["sku"])
        await _assert_sku_free(db, patch["sku"], exclude_id=product.id)

    if patch.get("slug"):
        patch["slug"] = await _resolve_product_slug(
            db,
            explicit=patch["slug"],
            name=patch.get("name") or product.name,
            exclude_id=product.id,
        )

    # The CHECK constraint compares the two stored values, so a patch that
    # touches only one of them still has to be validated against the other.
    new_price = patch.get("price", product.price)
    new_old_price = patch.get("old_price", product.old_price)
    if new_old_price is not None and new_old_price <= new_price:
        raise ValidationError(
            "The old price must be higher than the current price",
            code="INVALID_OLD_PRICE",
            details=[{"field": "oldPrice"}],
        )

    tracked = [column.name for column in Product.__table__.columns if column.name != "search_text"]
    before = audit.snapshot(product, tracked)

    for key, value in patch.items():
        setattr(product, key, value)

    # Anything that feeds the index must refresh it. Without this the product
    # stays in the catalogue and quietly stops being findable.
    if {"name", "short_description", "tags", "specs", "category_id", "brand_id"} & patch.keys():
        await _refresh_search_text(db, product)

    await db.flush()
    await db.refresh(product)
    after = audit.snapshot(product, tracked)
    return product, before, after


async def archive_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    """Retire a product. Also clears is_active so storefront queries need no change."""
    product = await db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
    if product.archived_at is not None:
        raise ConflictError("This product is already archived", code="ALREADY_ARCHIVED")

    product.archived_at = datetime.now(UTC)
    product.is_active = False
    await db.flush()
    return product


async def unarchive_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    """Bring a product back as a draft - deliberately not active.

    Reactivating straight to the storefront would republish prices and stock
    that nobody has looked at since it was retired.
    """
    product = await db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
    if product.archived_at is None:
        raise ConflictError("This product is not archived", code="NOT_ARCHIVED")

    product.archived_at = None
    product.is_active = False
    await db.flush()
    return product


async def delete_product(
    db: AsyncSession, storage: StorageBackend, product_id: uuid.UUID
) -> dict[str, Any]:
    """Permanently remove a product, with its images and its stock ledger.

    Refuses the moment the product appears in an order: `order_items.product_id`
    is ON DELETE RESTRICT, because what a customer actually bought must not be
    rewritten by a later tidy-up. The 409 names how many orders are in the way,
    and the answer there is archiving.

    For everything else - a product typed in twice, a draft that never went
    live, a test row - deleting is the honest operation. Archiving those would
    leave rows nobody will ever look at again.

    `inventory_movements` and `product_images` are ON DELETE CASCADE. A product
    that never sold has no stock history worth keeping, and the audit row this
    delete writes outlives the product either way.

    Returns a snapshot of what was removed, for that audit record.
    """
    product = await db.get(Product, product_id, options=[selectinload(Product.images)])
    if product is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")

    ordered = await db.scalar(
        select(func.count()).select_from(OrderItem).where(OrderItem.product_id == product_id)
    )
    if ordered:
        raise ConflictError(
            "This product appears in orders and can only be archived",
            code="PRODUCT_IN_USE",
            details={"ordersCount": int(ordered)},
        )

    snapshot = {
        "slug": product.slug,
        "name": product.name,
        "sku": product.sku,
        "stock": product.stock,
    }
    urls = [image.url for image in product.images]

    await db.delete(product)
    await db.flush()

    # Only after the row is gone: a failed delete must not leave the product
    # pointing at files that no longer exist.
    await discard_objects(db, storage, urls)
    return snapshot


async def duplicate_product(
    db: AsyncSession, product_id: uuid.UUID, *, actor_id: uuid.UUID | None
) -> Product:
    """Copy the content of a product, but not its images or its stock.

    Images are skipped because two products pointing at one storage object make
    deletion ambiguous later. Stock starts at zero because a copy has none.
    """
    source = await db.get(Product, product_id)
    if source is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")

    copy = Product(
        slug=await unique_slug(db, Product.slug, f"{source.slug}-copy", id_column=Product.id),
        sku=await _next_free_sku(db, source.sku),
        name=f"{source.name} (ასლი)",
        short_description=source.short_description,
        description=source.description,
        category_id=source.category_id,
        brand_id=source.brand_id,
        price=source.price,
        old_price=source.old_price,
        stock=0,
        low_stock_threshold=source.low_stock_threshold,
        specs=dict(source.specs or {}),
        tags=list(source.tags or []),
        is_active=False,
        is_featured=False,
        is_new=source.is_new,
    )
    db.add(copy)
    await db.flush()
    await _refresh_search_text(db, copy)
    await db.flush()
    return copy


async def _next_free_sku(db: AsyncSession, source_sku: str | None) -> str | None:
    """`SKU-COPY`, `SKU-COPY-2`... or None when the original had no SKU."""
    if not source_sku:
        return None
    base = f"{source_sku}-COPY"
    candidate = base
    suffix = 1
    while await db.scalar(
        select(func.count()).select_from(Product).where(Product.sku == candidate)
    ):
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate[:64]
