"""Admin categories and brands.

What it covers: the rules that protect the storefront - filter config must keep
the shape FilterSidebar reads, the category tree cannot contain a cycle, and
nothing in use can be deleted. Also the shared slug utility, including the
Georgian transliteration cases from the brief.
"""

import httpx
import pytest
from app.db.models import ROLE_ADMIN, AdminAuditLog, Category
from app.services.slug import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

ADMIN = "/api/v1/admin"


@pytest.fixture
async def headers(db: AsyncSession) -> dict[str, str]:
    admin = await make_user(db, email="catalog-admin@voltbox.ge", role=ROLE_ADMIN)
    return auth_header(admin)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("ტელეფონები", "teleponebi"),
        ("სმარტ საათები", "smart-saatebi"),
        ("iPhone 15 Pro", "iphone-15-pro"),
        ("Power Bank-ები", "power-bank-ebi"),
        ("  ორმაგი   ჰარები  ", "ormagi-harebi"),
        ("Café Noël", "cafe-noel"),
        ("!!!", ""),
    ],
)
def test_slugify(source: str, expected: str) -> None:
    assert slugify(source) == expected


async def test_create_category_generates_a_slug_from_the_name(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{ADMIN}/categories",
        headers=headers,
        json={"name": "ყურსასმენები", "icon": "Headphones"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == "qursasmenebi"
    assert body["productsCount"] == 0
    assert body["childrenCount"] == 0


async def test_an_explicit_duplicate_slug_is_a_conflict_not_a_rename(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    await make_category(db, slug="phones")

    response = await client.post(
        f"{ADMIN}/categories", headers=headers, json={"name": "სხვა", "slug": "phones"}
    )

    # Silently renaming to phones-2 would hand the author a URL they never chose.
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SLUG_TAKEN"


async def test_a_generated_slug_is_made_unique(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    await make_category(db, slug="qursasmenebi")

    response = await client.post(
        f"{ADMIN}/categories", headers=headers, json={"name": "ყურსასმენები"}
    )

    assert response.status_code == 201
    assert response.json()["slug"] == "qursasmenebi-2"


VALID_FILTERS = [
    {"key": "brand", "label": "ბრენდი", "type": "checkbox"},
    {"key": "specs.ram", "label": "RAM", "type": "checkbox"},
    {"key": "specs.network", "label": "5G", "type": "toggle", "match": "5G"},
    {"key": "specs.fastCharge", "label": "სწრაფი", "type": "toggle", "match": True},
    {"key": "specs.color", "label": "ფერი", "type": "swatch"},
]


async def test_filters_round_trip_in_the_shape_the_storefront_reads(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{ADMIN}/categories",
        headers=headers,
        json={"name": "ტელეფონები", "filters": VALID_FILTERS},
    )

    assert response.status_code == 201
    stored = response.json()["filters"]
    assert stored == VALID_FILTERS
    # `match` must not appear on non-toggle entries, or the storefront would
    # carry a value it silently ignores.
    assert "match" not in stored[0]
    assert stored[3]["match"] is True


@pytest.mark.parametrize(
    "bad_filter",
    [
        # A bare spec key: the storefront resolves "specs.<key>", so this filter
        # would render and then match nothing.
        {"key": "ram", "label": "RAM", "type": "checkbox"},
        {"key": "specs.ram", "label": "RAM", "type": "toggle"},
        {"key": "specs.ram", "label": "RAM", "type": "checkbox", "match": "x"},
        {"key": "specs.", "label": "x", "type": "checkbox"},
        {"key": "brand", "label": "b", "type": "radio"},
        {"key": "brand", "type": "checkbox"},
    ],
)
async def test_invalid_filter_config_is_rejected(
    client: httpx.AsyncClient, headers: dict[str, str], bad_filter: dict[str, object]
) -> None:
    response = await client.post(
        f"{ADMIN}/categories",
        headers=headers,
        json={"name": "ტესტი", "filters": [bad_filter]},
    )

    # This project answers 400 for validation, not FastAPI's default 422.
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_a_category_cannot_be_its_own_parent(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, slug="self-parent")

    response = await client.patch(
        f"{ADMIN}/categories/{category.id}", headers=headers, json={"parentId": str(category.id)}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CATEGORY_SELF_PARENT"


async def test_nesting_deeper_than_the_storefront_renders_is_refused(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    root = await make_category(db, slug="root")
    child = await make_category(db, slug="child")
    child.parent_id = root.id
    await db.flush()

    response = await client.post(
        f"{ADMIN}/categories",
        headers=headers,
        json={"name": "grandchild", "parentId": str(child.id)},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CATEGORY_TOO_DEEP"


async def test_deleting_a_category_with_products_is_refused_with_counts(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, slug="busy")
    brand = await make_brand(db, "BusyBrand")
    await make_product(db, category, brand, slug="busy-1")

    response = await client.delete(f"{ADMIN}/categories/{category.id}", headers=headers)

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "CATEGORY_IN_USE"
    assert body["details"]["productsCount"] == 1


async def test_an_empty_category_can_be_deleted(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, slug="disposable")

    response = await client.delete(f"{ADMIN}/categories/{category.id}", headers=headers)

    assert response.status_code == 204
    assert await db.get(Category, category.id) is None


async def test_brand_counts_come_from_one_aggregate(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, slug="counted")
    apple = await make_brand(db, "Apple")
    await make_brand(db, "Empty")
    await make_product(db, category, apple, slug="c-1")
    await make_product(db, category, apple, slug="c-2")

    response = await client.get(f"{ADMIN}/brands", headers=headers)

    assert response.status_code == 200
    counts = {row["name"]: row["productsCount"] for row in response.json()}
    assert counts["Apple"] == 2
    assert counts["Empty"] == 0


async def test_duplicate_brand_name_is_a_conflict(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    await make_brand(db, "Anker")

    response = await client.post(f"{ADMIN}/brands", headers=headers, json={"name": "Anker"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "BRAND_NAME_TAKEN"


async def test_a_brand_with_products_cannot_be_deleted(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, slug="brandy")
    brand = await make_brand(db, "InUse")
    await make_product(db, category, brand, slug="b-1")

    response = await client.delete(f"{ADMIN}/brands/{brand.id}", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "BRAND_IN_USE"
    assert response.json()["error"]["details"]["productsCount"] == 1


async def test_updating_a_brand_records_only_what_changed(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    brand = await make_brand(db, "Hoco", country="ჩინეთი")

    response = await client.patch(
        f"{ADMIN}/brands/{brand.id}", headers=headers, json={"country": "იაპონია"}
    )

    assert response.status_code == 200
    assert response.json()["country"] == "იაპონია"

    entry = await db.scalar(
        select(AdminAuditLog).where(
            AdminAuditLog.entity_type == "brand", AdminAuditLog.entity_id == str(brand.id)
        )
    )
    assert entry is not None
    assert entry.action == "brand.update"
    # Only the changed field, not every column.
    assert entry.changes == {"country": ["ჩინეთი", "იაპონია"]}


async def test_an_update_that_changes_nothing_writes_no_audit_row(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    brand = await make_brand(db, "Same", country="აშშ")

    response = await client.patch(
        f"{ADMIN}/brands/{brand.id}", headers=headers, json={"country": "აშშ"}
    )

    assert response.status_code == 200
    entries = (
        await db.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_id == str(brand.id)))
    ).all()
    # A trail full of empty entries is harder to read than one without them.
    assert list(entries) == []


async def test_creating_a_category_is_audited_with_the_actor(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    response = await client.post(f"{ADMIN}/categories", headers=headers, json={"name": "აუდიტი"})
    category_id = response.json()["id"]

    entry = await db.scalar(select(AdminAuditLog).where(AdminAuditLog.entity_id == category_id))
    assert entry is not None
    assert entry.action == "category.create"
    assert entry.actor_id is not None


async def test_unknown_fields_are_rejected_rather_than_ignored(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    """extra=forbid: a typo must fail loudly instead of being dropped."""
    response = await client.post(
        f"{ADMIN}/categories", headers=headers, json={"name": "ოკ", "prodctsCount": 5}
    )

    assert response.status_code == 400
