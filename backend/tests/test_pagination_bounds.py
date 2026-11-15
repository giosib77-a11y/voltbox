"""Every `page` input has an upper bound (A-038).

Without one, `page=9223372036854775807` makes OFFSET `(page - 1) * limit` overflow
int64 and asyncpg answered 500, on a public endpoint with no auth. The bound is a
400 `VALIDATION_ERROR` (not a silent clamp), and the last allowed page still works.
"""

import httpx
import pytest
from app.core.pagination import MAX_PAGE, PageParams
from app.db.models import ROLE_ADMIN
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

API = "/api/v1"
INT64_MAX = 9223372036854775807

#: (path, needs admin) - `{product}` is replaced with a real product id.
PAGED_ROUTES = [
    ("/products", False),
    ("/admin/products", True),
    ("/admin/orders", True),
    ("/admin/customers", True),
    ("/admin/inventory", True),
    ("/admin/inventory/{product}/movements", True),
]


@pytest.fixture
async def setup(db: AsyncSession) -> tuple[dict[str, str], str]:
    admin = await make_user(db, email="pagination-admin@voltbox.ge", role=ROLE_ADMIN)
    category = await make_category(db, slug="cat-pagination")
    brand = await make_brand(db, "Brand-pagination")
    product = await make_product(db, category, brand, slug="pagination-product")
    return auth_header(admin), str(product.id)


async def _get(
    client: httpx.AsyncClient,
    path: str,
    admin: bool,
    setup: tuple[dict[str, str], str],
    page: int,
) -> httpx.Response:
    headers, product_id = setup
    return await client.get(
        API + path.replace("{product}", product_id),
        headers=headers if admin else None,
        params={"page": page},
    )


@pytest.mark.parametrize(("path", "admin"), PAGED_ROUTES)
async def test_the_last_allowed_page_is_served(
    client: httpx.AsyncClient, setup: tuple[dict[str, str], str], path: str, admin: bool
) -> None:
    response = await _get(client, path, admin, setup, MAX_PAGE)
    assert response.status_code == 200
    assert response.json()["page"] == MAX_PAGE


@pytest.mark.parametrize("page", [MAX_PAGE + 1, INT64_MAX, INT64_MAX + 1])
@pytest.mark.parametrize(("path", "admin"), PAGED_ROUTES)
async def test_a_page_past_the_bound_is_a_400_not_a_500(
    client: httpx.AsyncClient,
    setup: tuple[dict[str, str], str],
    path: str,
    admin: bool,
    page: int,
) -> None:
    response = await _get(client, path, admin, setup, page)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_the_shared_page_params_enforce_the_same_bound() -> None:
    assert PageParams(page=MAX_PAGE).offset >= 0
    with pytest.raises(ValidationError):
        PageParams(page=MAX_PAGE + 1)
