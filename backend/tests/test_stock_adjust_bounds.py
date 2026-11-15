"""Bounds on the admin stock-adjust request.

What it covers: `change` is limited to +-100 000 so a huge value is a 400, not an
int4 overflow 500 from Postgres. Zero keeps its established 400 EMPTY_ADJUSTMENT.
"""

import httpx
import pytest
from app.db.models import ROLE_ADMIN, InventoryMovement, Product
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

ADMIN = "/api/v1/admin"


@pytest.fixture
async def headers(db: AsyncSession) -> dict[str, str]:
    admin = await make_user(db, email="adjust-bounds-admin@voltbox.ge", role=ROLE_ADMIN)
    return auth_header(admin)


async def _product(db: AsyncSession, *, stock: int) -> Product:
    category = await make_category(db, slug="adj-bounds")
    brand = await make_brand(db, "AdjBoundsBrand")
    return await make_product(db, category, brand, slug="adj-bounds-1", stock=stock)


async def _adjust(
    client: httpx.AsyncClient, headers: dict[str, str], product: Product, change: int
) -> httpx.Response:
    return await client.post(
        f"{ADMIN}/inventory/{product.id}/adjust",
        headers=headers,
        json={"change": change, "reason": "restock"},
    )


async def test_the_largest_positive_adjustment_is_accepted(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    product = await _product(db, stock=5)

    response = await _adjust(client, headers, product, 100_000)

    assert response.status_code == 200
    assert response.json()["stock"] == 100_005


async def test_the_largest_negative_adjustment_is_accepted(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    product = await _product(db, stock=100_000)

    response = await _adjust(client, headers, product, -100_000)

    assert response.status_code == 200
    assert response.json()["stock"] == 0


@pytest.mark.parametrize("change", [100_001, -100_001, 3_000_000_000, -3_000_000_000])
async def test_an_out_of_range_adjustment_is_a_validation_error(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    db: AsyncSession,
    change: int,
) -> None:
    product = await _product(db, stock=100_000)

    response = await _adjust(client, headers, product, change)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert await db.scalar(select(Product.stock).where(Product.id == product.id)) == 100_000
    movements = await db.scalar(
        select(func.count())
        .select_from(InventoryMovement)
        .where(InventoryMovement.product_id == product.id)
    )
    assert movements == 0


async def test_a_zero_adjustment_is_a_400_with_the_established_code(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    product = await _product(db, stock=5)

    response = await _adjust(client, headers, product, 0)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_ADJUSTMENT"
