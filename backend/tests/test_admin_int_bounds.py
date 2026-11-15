"""Upper bounds on the admin int fields that were bounded only below.

What it covers: initial `stock` and `lowStockThreshold` on a product, and
`position` on a category, are limited so an absurd value (3 000 000 000) is a 400
VALIDATION_ERROR instead of an int4 overflow 500 from Postgres. Nothing is written
when the request is refused. Negative values stay rejected by the existing `ge=0`.
"""

from typing import Any

import httpx
import pytest
from app.db.models import ROLE_ADMIN, Category, InventoryMovement, Product
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

ADMIN = "/api/v1/admin"
OVERFLOW = 3_000_000_000


@pytest.fixture
async def headers(db: AsyncSession) -> dict[str, str]:
    admin = await make_user(db, email="int-bounds-admin@voltbox.ge", role=ROLE_ADMIN)
    return auth_header(admin)


async def _product_payload(db: AsyncSession, **extra: Any) -> dict[str, Any]:
    category = await make_category(db, slug="int-bounds")
    brand = await make_brand(db, "IntBoundsBrand")
    return {
        "name": "Bounds phone",
        "slug": "bounds-phone",
        "categoryId": str(category.id),
        "brandId": str(brand.id),
        "price": "100.00",
        **extra,
    }


async def _existing_product(db: AsyncSession) -> Product:
    category = await make_category(db, slug="int-bounds-existing")
    brand = await make_brand(db, "IntBoundsOld")
    return await make_product(db, category, brand, slug="int-bounds-old", stock=5)


async def _count(db: AsyncSession, model: type) -> int:
    return int(await db.scalar(select(func.count()).select_from(model)) or 0)


def _assert_validation_error(response: httpx.Response) -> None:
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- product: initial stock -------------------------------------------------


async def test_the_largest_initial_stock_is_accepted_with_its_ledger_row(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    payload = await _product_payload(db, stock=100_000)

    response = await client.post(f"{ADMIN}/products", headers=headers, json=payload)

    assert response.status_code == 201
    assert response.json()["stock"] == 100_000
    assert await _count(db, InventoryMovement) == 1


@pytest.mark.parametrize("stock", [100_001, OVERFLOW])
async def test_an_initial_stock_over_the_limit_is_a_validation_error(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession, stock: int
) -> None:
    payload = await _product_payload(db, stock=stock)

    response = await client.post(f"{ADMIN}/products", headers=headers, json=payload)

    _assert_validation_error(response)
    assert await _count(db, Product) == 0
    assert await _count(db, InventoryMovement) == 0


# --- product: low stock threshold -------------------------------------------


async def test_the_largest_threshold_is_accepted_on_create(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    payload = await _product_payload(db, lowStockThreshold=100_000)

    response = await client.post(f"{ADMIN}/products", headers=headers, json=payload)

    assert response.status_code == 201
    assert response.json()["lowStockThreshold"] == 100_000


@pytest.mark.parametrize("threshold", [100_001, OVERFLOW])
async def test_a_threshold_over_the_limit_is_refused_on_create(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession, threshold: int
) -> None:
    payload = await _product_payload(db, lowStockThreshold=threshold)

    response = await client.post(f"{ADMIN}/products", headers=headers, json=payload)

    _assert_validation_error(response)
    assert await _count(db, Product) == 0


async def test_the_largest_threshold_is_accepted_on_update(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    product = await _existing_product(db)

    response = await client.patch(
        f"{ADMIN}/products/{product.id}", headers=headers, json={"lowStockThreshold": 100_000}
    )

    assert response.status_code == 200
    assert response.json()["lowStockThreshold"] == 100_000


@pytest.mark.parametrize("threshold", [100_001, OVERFLOW])
async def test_a_threshold_over_the_limit_is_refused_on_update(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession, threshold: int
) -> None:
    product = await _existing_product(db)
    before = product.low_stock_threshold

    response = await client.patch(
        f"{ADMIN}/products/{product.id}", headers=headers, json={"lowStockThreshold": threshold}
    )

    _assert_validation_error(response)
    stored = await db.scalar(
        select(Product.low_stock_threshold)
        .where(Product.id == product.id)
        .execution_options(populate_existing=True)
    )
    assert stored == before


# --- category: position -----------------------------------------------------


async def test_the_largest_position_is_accepted_on_create(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    response = await client.post(
        f"{ADMIN}/categories", headers=headers, json={"name": "Last", "position": 10_000}
    )

    assert response.status_code == 201
    assert response.json()["position"] == 10_000


@pytest.mark.parametrize("position", [10_001, OVERFLOW])
async def test_a_position_over_the_limit_is_refused_on_create(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession, position: int
) -> None:
    response = await client.post(
        f"{ADMIN}/categories", headers=headers, json={"name": "Far", "position": position}
    )

    _assert_validation_error(response)
    assert await _count(db, Category) == 0


async def test_the_largest_position_is_accepted_on_update(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, slug="pos-update-ok")

    response = await client.patch(
        f"{ADMIN}/categories/{category.id}", headers=headers, json={"position": 10_000}
    )

    assert response.status_code == 200
    assert response.json()["position"] == 10_000


@pytest.mark.parametrize("position", [10_001, OVERFLOW])
async def test_a_position_over_the_limit_is_refused_on_update(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession, position: int
) -> None:
    category = await make_category(db, slug="pos-update-bad")
    before = category.position

    response = await client.patch(
        f"{ADMIN}/categories/{category.id}", headers=headers, json={"position": position}
    )

    _assert_validation_error(response)
    stored = await db.scalar(
        select(Category.position)
        .where(Category.id == category.id)
        .execution_options(populate_existing=True)
    )
    assert stored == before
