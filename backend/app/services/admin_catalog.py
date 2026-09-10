"""Category and brand management for the admin panel.

What it does: create, update and delete categories and brands, with the rules
that keep the storefront intact - no cycles in the category tree, no deleting
something products still point at, and unique slugs.
Where it fits: called by the admin routes; shares slug generation with the
product endpoints via services/slug.py.
Notes: counts come from grouped aggregates rather than per-row queries. A
category list that issues one COUNT per row is fine with six categories and
unusable with two hundred.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import Brand, Category, Product
from app.services import audit
from app.services.slug import slugify, unique_slug

#: How deep the category tree may go. The storefront renders one level of
#: children; anything deeper would not be reachable in the UI.
MAX_CATEGORY_DEPTH = 2


async def _counts_by_category(
    db: AsyncSession,
) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
    """Product and child counts for every category, in two grouped queries."""
    product_rows = await db.execute(
        select(Product.category_id, func.count().label("hits")).group_by(Product.category_id)
    )
    child_rows = await db.execute(
        select(Category.parent_id, func.count().label("hits"))
        .where(Category.parent_id.is_not(None))
        .group_by(Category.parent_id)
    )
    products = {row[0]: int(row[1]) for row in product_rows}
    children = {row[0]: int(row[1]) for row in child_rows}
    return products, children


async def list_categories(db: AsyncSession) -> list[dict[str, Any]]:
    """Every category with its counts, ordered for a tree rendering."""
    categories = list(
        (await db.scalars(select(Category).order_by(Category.position, Category.name))).all()
    )
    products, children = await _counts_by_category(db)
    return [
        {
            **{c.name: getattr(category, c.name) for c in Category.__table__.columns},
            "products_count": products.get(category.id, 0),
            "children_count": children.get(category.id, 0),
        }
        for category in categories
    ]


async def get_category(db: AsyncSession, category_id: uuid.UUID) -> dict[str, Any]:
    category = await db.get(Category, category_id)
    if category is None:
        raise NotFoundError("Category not found", code="CATEGORY_NOT_FOUND")
    products, children = await _counts_by_category(db)
    return {
        **{c.name: getattr(category, c.name) for c in Category.__table__.columns},
        "products_count": products.get(category.id, 0),
        "children_count": children.get(category.id, 0),
    }


async def _assert_no_cycle(
    db: AsyncSession, category_id: uuid.UUID | None, parent_id: uuid.UUID | None
) -> None:
    """Walk up from the proposed parent; the category must not appear.

    A cycle would make the storefront's breadcrumb walk loop forever, and the
    depth check keeps the tree within what the UI can render.
    """
    if parent_id is None:
        return
    if category_id is not None and parent_id == category_id:
        raise ValidationError("A category cannot be its own parent", code="CATEGORY_SELF_PARENT")

    parent = await db.get(Category, parent_id)
    if parent is None:
        raise ValidationError("Parent category does not exist", code="PARENT_NOT_FOUND")

    depth = 1
    seen: set[uuid.UUID] = {parent.id}
    current = parent
    while current.parent_id is not None:
        if current.parent_id == category_id:
            raise ValidationError("This would create a cycle", code="CATEGORY_CYCLE")
        if current.parent_id in seen:
            # Existing data is already broken; refuse rather than loop.
            raise ValidationError("The category tree contains a cycle", code="CATEGORY_CYCLE")
        seen.add(current.parent_id)
        nxt = await db.get(Category, current.parent_id)
        if nxt is None:
            break
        current = nxt
        depth += 1

    if depth >= MAX_CATEGORY_DEPTH:
        raise ValidationError(
            f"Categories may nest at most {MAX_CATEGORY_DEPTH} levels deep",
            code="CATEGORY_TOO_DEEP",
        )


async def _resolve_slug(
    db: AsyncSession,
    column: Any,
    id_column: Any,
    *,
    explicit: str | None,
    name: str,
    exclude_id: uuid.UUID | None = None,
) -> str:
    """An explicit slug is taken literally; a missing one is generated.

    A duplicate explicit slug is a 409 rather than a silent rename: quietly
    turning `iphone-15` into `iphone-15-2` produces a URL the author did not ask
    for and will not find later.
    """
    if explicit:
        candidate = slugify(explicit)
        if not candidate:
            raise ValidationError("Slug contains no usable characters", code="INVALID_SLUG")
        stmt = select(func.count()).select_from(column.parent).where(column == candidate)
        if exclude_id is not None:
            stmt = stmt.where(id_column != exclude_id)
        if await db.scalar(stmt):
            raise ConflictError(
                "This slug is already taken",
                code="SLUG_TAKEN",
                details=[{"field": "slug", "value": candidate}],
            )
        return candidate

    return await unique_slug(db, column, slugify(name), exclude_id=exclude_id, id_column=id_column)


async def create_category(db: AsyncSession, payload: dict[str, Any]) -> Category:
    await _assert_no_cycle(db, None, payload.get("parent_id"))
    slug = await _resolve_slug(
        db, Category.slug, Category.id, explicit=payload.get("slug"), name=payload["name"]
    )
    category = Category(
        slug=slug,
        name=payload["name"],
        short_name=payload.get("short_name") or payload["name"],
        description=payload.get("description") or "",
        icon=payload.get("icon") or "Package",
        parent_id=payload.get("parent_id"),
        position=payload.get("position") or 0,
        image_url=payload.get("image_url"),
        filters=payload.get("filters") or [],
    )
    db.add(category)
    await db.flush()
    return category


async def update_category(
    db: AsyncSession, category_id: uuid.UUID, patch: dict[str, Any]
) -> tuple[Category, dict[str, Any], dict[str, Any]]:
    """Applies a partial update. Returns the row plus before/after for auditing."""
    category = await db.get(Category, category_id)
    if category is None:
        raise NotFoundError("Category not found", code="CATEGORY_NOT_FOUND")

    if "parent_id" in patch:
        await _assert_no_cycle(db, category.id, patch["parent_id"])

    if patch.get("slug"):
        patch["slug"] = await _resolve_slug(
            db,
            Category.slug,
            Category.id,
            explicit=patch["slug"],
            name=patch.get("name") or category.name,
            exclude_id=category.id,
        )

    tracked = [column.name for column in Category.__table__.columns]
    before = audit.snapshot(category, tracked)
    for key, value in patch.items():
        setattr(category, key, value)
    await db.flush()
    # `updated_at` has a server-side onupdate, so SQLAlchemy expires it after the
    # flush regardless of expire_on_commit. Reading it later would trigger a
    # lazy refresh - synchronous IO inside async code, which raises
    # MissingGreenlet. Loading it here keeps every later read safe.
    await db.refresh(category)
    after = audit.snapshot(category, tracked)
    return category, before, after


async def delete_category(db: AsyncSession, category_id: uuid.UUID) -> None:
    """Refuses while anything still points at the category.

    Products use ON DELETE RESTRICT, so the database would refuse anyway - but a
    409 that says how many products and children are in the way is far more
    useful than a foreign-key error.
    """
    category = await db.get(Category, category_id)
    if category is None:
        raise NotFoundError("Category not found", code="CATEGORY_NOT_FOUND")

    products = await db.scalar(
        select(func.count()).select_from(Product).where(Product.category_id == category_id)
    )
    children = await db.scalar(
        select(func.count()).select_from(Category).where(Category.parent_id == category_id)
    )
    if products or children:
        raise ConflictError(
            "This category is still in use",
            code="CATEGORY_IN_USE",
            details={"productsCount": int(products or 0), "childrenCount": int(children or 0)},
        )

    await db.delete(category)
    await db.flush()


async def list_brands(db: AsyncSession) -> list[dict[str, Any]]:
    """Brands with product counts, in one grouped query rather than one per row."""
    brands = list((await db.scalars(select(Brand).order_by(Brand.name))).all())
    rows = await db.execute(
        select(Product.brand_id, func.count().label("hits")).group_by(Product.brand_id)
    )
    counts = {row[0]: int(row[1]) for row in rows}
    return [
        {
            **{c.name: getattr(brand, c.name) for c in Brand.__table__.columns},
            "products_count": counts.get(brand.id, 0),
        }
        for brand in brands
    ]


async def get_brand(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = await db.get(Brand, brand_id)
    if brand is None:
        raise NotFoundError("Brand not found", code="BRAND_NOT_FOUND")
    count = await db.scalar(
        select(func.count()).select_from(Product).where(Product.brand_id == brand_id)
    )
    return {
        **{c.name: getattr(brand, c.name) for c in Brand.__table__.columns},
        "products_count": int(count or 0),
    }


async def create_brand(db: AsyncSession, payload: dict[str, Any]) -> Brand:
    existing = await db.scalar(select(Brand).where(Brand.name == payload["name"]))
    if existing is not None:
        raise ConflictError(
            "A brand with this name already exists",
            code="BRAND_NAME_TAKEN",
            details=[{"field": "name"}],
        )
    slug = await _resolve_slug(
        db, Brand.slug, Brand.id, explicit=payload.get("slug"), name=payload["name"]
    )
    brand = Brand(
        slug=slug,
        name=payload["name"],
        country=payload.get("country"),
        logo_url=payload.get("logo_url"),
    )
    db.add(brand)
    await db.flush()
    return brand


async def update_brand(
    db: AsyncSession, brand_id: uuid.UUID, patch: dict[str, Any]
) -> tuple[Brand, dict[str, Any], dict[str, Any]]:
    brand = await db.get(Brand, brand_id)
    if brand is None:
        raise NotFoundError("Brand not found", code="BRAND_NOT_FOUND")

    if "name" in patch and patch["name"] != brand.name:
        clash = await db.scalar(
            select(Brand).where(Brand.name == patch["name"], Brand.id != brand_id)
        )
        if clash is not None:
            raise ConflictError(
                "A brand with this name already exists",
                code="BRAND_NAME_TAKEN",
                details=[{"field": "name"}],
            )

    if patch.get("slug"):
        patch["slug"] = await _resolve_slug(
            db,
            Brand.slug,
            Brand.id,
            explicit=patch["slug"],
            name=patch.get("name") or brand.name,
            exclude_id=brand.id,
        )

    tracked = [column.name for column in Brand.__table__.columns]
    before = audit.snapshot(brand, tracked)
    for key, value in patch.items():
        setattr(brand, key, value)
    await db.flush()
    # `updated_at` has a server-side onupdate, so SQLAlchemy expires it after the
    # flush regardless of expire_on_commit. Reading it later would trigger a
    # lazy refresh - synchronous IO inside async code, which raises
    # MissingGreenlet. Loading it here keeps every later read safe.
    await db.refresh(brand)
    after = audit.snapshot(brand, tracked)
    return brand, before, after


async def delete_brand(db: AsyncSession, brand_id: uuid.UUID) -> None:
    brand = await db.get(Brand, brand_id)
    if brand is None:
        raise NotFoundError("Brand not found", code="BRAND_NOT_FOUND")

    count = await db.scalar(
        select(func.count()).select_from(Product).where(Product.brand_id == brand_id)
    )
    if count:
        raise ConflictError(
            "This brand still has products",
            code="BRAND_IN_USE",
            details={"productsCount": int(count)},
        )

    await db.delete(brand)
    await db.flush()
