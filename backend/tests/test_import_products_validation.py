"""`import_products.validate` against the stock and threshold limits (A-078).

What it covers: a row whose `stock` is past MAX_STOCK (A-072) or whose
`lowStockThreshold` is past MAX_LOW_STOCK_THRESHOLD (A-073), negative, or not a
whole number is refused with a ProductImportError that names the slug, the field
and the limit - in `validate()` and so in `load_rows()` and `--dry-run`, before a
session is opened. The limits themselves are accepted.

Why it exists: `"stock": 2000000` and `"lowStockThreshold": 3000000000` used to get
"validation passed" on --dry-run, and the real run then stopped with a raw
traceback (STOCK_LIMIT_EXCEEDED from `adjust_stock`, an int4 overflow at flush).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from app.db.models import InventoryMovement, Product
from app.schemas.admin_product import MAX_LOW_STOCK_THRESHOLD
from app.services.inventory import MAX_STOCK
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import load_script, make_brand, make_category

importer = load_script("import_products")


def row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "slug": "validated-a",
        "name": "Validated A",
        "category": "scripted",
        "brand": "ScriptBrand",
        "price": 100,
    }
    return {**base, **overrides}


@pytest.mark.parametrize("stock", [MAX_STOCK + 1, 2_000_000, 3_000_000_000])
def test_a_stock_past_the_ceiling_is_refused_naming_field_and_limit(stock: int) -> None:
    with pytest.raises(importer.ProductImportError) as caught:
        importer.validate(row(stock=stock), 1)

    message = str(caught.value)
    assert "validated-a" in message
    assert "`stock`" in message
    assert str(stock) in message
    assert str(MAX_STOCK) in message


def test_a_negative_stock_is_refused() -> None:
    with pytest.raises(importer.ProductImportError, match="`stock`"):
        importer.validate(row(stock=-1), 1)


@pytest.mark.parametrize("stock", [0, 1, MAX_STOCK])
def test_a_stock_up_to_and_including_the_ceiling_is_accepted(stock: int) -> None:
    importer.validate(row(stock=stock), 1)


def test_a_missing_stock_and_threshold_fall_back_to_the_defaults() -> None:
    importer.validate(row(), 1)


@pytest.mark.parametrize("threshold", [MAX_LOW_STOCK_THRESHOLD + 1, 3_000_000_000])
def test_a_threshold_past_the_limit_is_refused_naming_field_and_limit(threshold: int) -> None:
    with pytest.raises(importer.ProductImportError) as caught:
        importer.validate(row(lowStockThreshold=threshold), 1)

    message = str(caught.value)
    assert "validated-a" in message
    assert "`lowStockThreshold`" in message
    assert str(threshold) in message
    assert str(MAX_LOW_STOCK_THRESHOLD) in message


def test_a_negative_threshold_is_refused() -> None:
    with pytest.raises(importer.ProductImportError, match="`lowStockThreshold`"):
        importer.validate(row(lowStockThreshold=-1), 1)


@pytest.mark.parametrize("threshold", [0, MAX_LOW_STOCK_THRESHOLD])
def test_a_threshold_up_to_and_including_the_limit_is_accepted(threshold: int) -> None:
    importer.validate(row(lowStockThreshold=threshold), 1)


@pytest.mark.parametrize("field", ["stock", "lowStockThreshold"])
@pytest.mark.parametrize("value", ["abc", "1.5", 1.5, True, False, None, [], {}])
def test_a_value_that_is_not_a_whole_number_is_a_clear_error_not_a_traceback(
    field: str, value: Any
) -> None:
    """`true` is refused rather than read as 1: in a stock column it is a typo."""
    with pytest.raises(importer.ProductImportError) as caught:
        importer.validate(row(**{field: value}), 1)

    assert f"`{field}`" in str(caught.value)
    assert "validated-a" in str(caught.value)


@pytest.mark.parametrize(
    ("value", "expected"), [(5, 5), (5.0, 5), ("5", 5), (" 7 ", 7), (0, 0), ("-3", -3)]
)
def test_to_int_accepts_whole_numbers_in_the_forms_a_json_file_has(
    value: Any, expected: int
) -> None:
    assert importer.to_int(value, "stock", "validated-a") == expected


def test_load_rows_refuses_a_file_with_one_invalid_row_before_any_database_work(
    tmp_path: Path,
) -> None:
    """`load_rows` is synchronous and takes no session: it cannot write anything.
    The invalid row is the second of three, so the refusal is for the file, not
    only for the first row."""
    path = tmp_path / "products.json"
    path.write_text(
        json.dumps(
            {
                "products": [
                    row(slug="fine-1", stock=5),
                    row(slug="too-much", stock=2_000_000),
                    row(slug="fine-2", stock=5),
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(importer.ProductImportError, match="too-much"):
        importer.load_rows(path)


def test_load_rows_accepts_a_file_whose_rows_sit_exactly_on_the_limits(tmp_path: Path) -> None:
    path = tmp_path / "products.json"
    path.write_text(
        json.dumps([row(stock=MAX_STOCK, lowStockThreshold=MAX_LOW_STOCK_THRESHOLD)]),
        encoding="utf-8",
    )

    assert len(importer.load_rows(path)) == 1


async def test_importing_a_row_at_exactly_the_ceiling_works(db: AsyncSession) -> None:
    category = await make_category(db, slug="import-limits")
    brand = await make_brand(db, "ImportLimitsBrand")
    full = row(
        slug="at-the-ceiling",
        category=category.slug,
        brand=brand.name,
        stock=MAX_STOCK,
        lowStockThreshold=MAX_LOW_STOCK_THRESHOLD,
    )

    importer.validate(full, 1)
    await importer.import_one(db, full, allow_create_brands=False)
    await db.flush()

    product = await db.scalar(select(Product).where(Product.slug == "at-the-ceiling"))
    assert product is not None
    assert product.stock == MAX_STOCK
    assert product.low_stock_threshold == MAX_LOW_STOCK_THRESHOLD
    changes = (
        await db.scalars(
            select(InventoryMovement.change).where(InventoryMovement.product_id == product.id)
        )
    ).all()
    assert list(changes) == [MAX_STOCK]
