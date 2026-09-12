"""seed.py and import_products.py, against the stock ledger.

What it covers: the single rule the whole inventory story rests on - every
change to `products.stock` goes through `adjust_stock`, so the ledger can always
explain the number. Both scripts once wrote the column directly, which left 61
products with stock and zero movements: nothing was broken to look at, and the
arithmetic simply would not have reconciled months later.

That was fixed by hand and nothing guarded it, because the scripts are not
imported anywhere pytest reaches. These tests import them by path and call the
functions that write products, so a future edit that goes back to
`product.stock = n` fails here rather than in production data.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from app.db.models import InventoryMovement, Product
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_brand, make_category

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name: str) -> ModuleType:
    """Import a file from scripts/, which is not a package."""
    spec = importlib.util.spec_from_file_location(f"voltbox_script_{name}", SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


async def ledger_mismatches(db: AsyncSession) -> list[tuple[str, int, int]]:
    """Products whose stock is not the sum of their movements."""
    rows = (
        await db.execute(
            select(
                Product.slug,
                Product.stock,
                func.coalesce(
                    select(func.sum(InventoryMovement.change))
                    .where(InventoryMovement.product_id == Product.id)
                    .scalar_subquery(),
                    0,
                ).label("ledger"),
            )
        )
    ).all()
    return [(r.slug, r.stock, int(r.ledger)) for r in rows if r.stock != int(r.ledger)]


@pytest.fixture
async def catalogue(db: AsyncSession) -> dict[str, Any]:
    category = await make_category(db, slug="scripted")
    brand = await make_brand(db, "ScriptBrand")
    await db.flush()
    return {"category": category, "brand": brand}


def seed_row(slug: str, stock: int, category: str, brand: str) -> dict[str, Any]:
    return {
        "id": slug,
        "slug": slug,
        "name": f"Seeded {slug}",
        "category": category,
        "brand": brand,
        "price": 100,
        "stock": stock,
        "createdAt": "2026-01-01T00:00:00Z",
    }


async def test_seed_writes_stock_through_the_ledger(
    db: AsyncSession, catalogue: dict[str, Any]
) -> None:
    seed = load_script("seed")
    categories = {catalogue["category"].slug: catalogue["category"]}
    brands = {catalogue["brand"].name: catalogue["brand"]}
    rows = [seed_row("scripted-a", 7, catalogue["category"].slug, catalogue["brand"].name)]

    await seed.upsert_products(db, rows, categories, brands)
    await db.flush()

    assert await ledger_mismatches(db) == []
    movements = (
        await db.scalars(select(InventoryMovement.change).order_by(InventoryMovement.created_at))
    ).all()
    assert list(movements) == [7]


async def test_re_seeding_records_the_difference_rather_than_overwriting(
    db: AsyncSession, catalogue: dict[str, Any]
) -> None:
    """Re-running an import is a correction, not a silent reset.

    Overwriting the column would leave the ledger claiming seven units while
    the product held three, and nothing would say where the four went.
    """
    seed = load_script("seed")
    categories = {catalogue["category"].slug: catalogue["category"]}
    brands = {catalogue["brand"].name: catalogue["brand"]}
    slug, category, brand = "scripted-b", catalogue["category"].slug, catalogue["brand"].name

    await seed.upsert_products(db, [seed_row(slug, 7, category, brand)], categories, brands)
    await db.flush()
    await seed.upsert_products(db, [seed_row(slug, 3, category, brand)], categories, brands)
    await db.flush()

    assert await ledger_mismatches(db) == []
    changes = (
        await db.scalars(select(InventoryMovement.change).order_by(InventoryMovement.created_at))
    ).all()
    assert list(changes) == [7, -4]


async def test_import_products_writes_stock_through_the_ledger(
    db: AsyncSession, catalogue: dict[str, Any]
) -> None:
    importer = load_script("import_products")
    row = {
        "slug": "imported-a",
        "name": "Imported A",
        "category": catalogue["category"].slug,
        "brand": catalogue["brand"].name,
        "price": 250,
        "stock": 5,
    }

    await importer.import_one(db, row, allow_create_brands=False)
    await db.flush()

    assert await ledger_mismatches(db) == []
    changes = (
        await db.scalars(select(InventoryMovement.change).order_by(InventoryMovement.created_at))
    ).all()
    assert list(changes) == [5]


async def test_an_unchanged_stock_writes_no_movement(
    db: AsyncSession, catalogue: dict[str, Any]
) -> None:
    """A no-op import must not fill the ledger with zero-sized corrections."""
    importer = load_script("import_products")
    row = {
        "slug": "imported-b",
        "name": "Imported B",
        "category": catalogue["category"].slug,
        "brand": catalogue["brand"].name,
        "price": 250,
        "stock": 4,
    }

    await importer.import_one(db, row, allow_create_brands=False)
    await db.flush()
    await importer.import_one(db, row, allow_create_brands=False)
    await db.flush()

    assert await ledger_mismatches(db) == []
    total = await db.scalar(select(func.count()).select_from(InventoryMovement))
    assert total == 1
