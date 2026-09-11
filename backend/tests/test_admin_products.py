"""Admin product endpoints.

What it covers: the rules that keep the catalogue coherent - SKU and slug
uniqueness, price sanity, stock only through the ledger, archiving as something
distinct from deactivating, deleting as something distinct from both, and above
all that the search index is refreshed on every write path.

That last one is the failure this codebase is most exposed to: a product with a
stale search_text appears in the catalogue and is simply never found, with no
error anywhere.
"""

import uuid

import httpx
import pytest
from app.db.models import ROLE_ADMIN, AdminAuditLog, InventoryMovement, Product
from app.services import order as order_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

ADMIN = "/api/v1/admin"
STORE = "/api/v1"


@pytest.fixture
async def headers(db: AsyncSession) -> dict[str, str]:
    admin = await make_user(db, email="product-admin@voltbox.ge", role=ROLE_ADMIN)
    return auth_header(admin)


@pytest.fixture
async def context(db: AsyncSession) -> dict[str, str]:
    category = await make_category(db, slug="phones")
    brand = await make_brand(db, "Apple")
    return {"categoryId": str(category.id), "brandId": str(brand.id)}


def payload(context: dict[str, str], **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "iPhone 15 Pro",
        "categoryId": context["categoryId"],
        "brandId": context["brandId"],
        "price": "3499.00",
        "shortDescription": "ტიტანის კორპუსი",
        "specs": {"ram": "8 GB", "color": "შავი"},
        "tags": ["ახალი"],
        "stock": 5,
    }
    base.update(overrides)
    return base


async def test_create_generates_a_slug_and_starts_inactive(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    response = await client.post(f"{ADMIN}/products", headers=headers, json=payload(context))

    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == "iphone-15-pro"
    # A new product is a draft until someone decides to publish it.
    assert body["isActive"] is False
    assert body["stock"] == 5
    assert body["stockStatus"] == "ok"


async def test_initial_stock_goes_through_the_ledger(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str], db: AsyncSession
) -> None:
    response = await client.post(f"{ADMIN}/products", headers=headers, json=payload(context))
    product_id = response.json()["id"]

    movements = list(
        (
            await db.scalars(
                select(InventoryMovement).where(InventoryMovement.product_id == product_id)
            )
        ).all()
    )
    # Even an opening balance has a movement explaining where it came from.
    assert len(movements) == 1
    assert movements[0].reason == "initial"
    assert (movements[0].previous_stock, movements[0].change, movements[0].new_stock) == (0, 5, 5)


async def test_stock_cannot_be_written_through_the_product_endpoint(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str], db: AsyncSession
) -> None:
    created = await client.post(f"{ADMIN}/products", headers=headers, json=payload(context))
    product_id = created.json()["id"]

    response = await client.patch(
        f"{ADMIN}/products/{product_id}", headers=headers, json={"stock": 999}
    )

    # extra=forbid: the field does not exist on ProductUpdate, so this is a loud
    # 400 rather than a silently ignored write that leaves the ledger incomplete.
    assert response.status_code == 400
    assert await db.scalar(select(Product.stock).where(Product.id == product_id)) == 5


async def test_a_duplicate_sku_is_a_conflict(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    await client.post(f"{ADMIN}/products", headers=headers, json=payload(context, sku="A-1"))

    response = await client.post(
        f"{ADMIN}/products",
        headers=headers,
        json=payload(context, name="სხვა", sku="a-1"),
    )

    # SKUs are normalized, so A-1 and a-1 are the same article.
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SKU_TAKEN"


async def test_old_price_must_exceed_price(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    response = await client.post(
        f"{ADMIN}/products",
        headers=headers,
        json=payload(context, price="100.00", oldPrice="90.00"),
    )

    assert response.status_code == 400


async def test_patching_only_the_price_is_still_checked_against_the_stored_old_price(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    created = await client.post(
        f"{ADMIN}/products",
        headers=headers,
        json=payload(context, price="100.00", oldPrice="150.00"),
    )
    product_id = created.json()["id"]

    # Raising the price above the stored old price would violate the CHECK
    # constraint; the service compares against what is stored, not only against
    # what arrived in this request.
    response = await client.patch(
        f"{ADMIN}/products/{product_id}", headers=headers, json={"price": "200.00"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_OLD_PRICE"


@pytest.mark.parametrize(
    "specs",
    [
        {"ram": {"nested": "object"}},
        {"ram": ["a", "list"]},
        {"": "empty key"},
    ],
)
async def test_specs_must_be_a_flat_object(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str], specs: dict
) -> None:
    response = await client.post(
        f"{ADMIN}/products", headers=headers, json=payload(context, specs=specs)
    )

    # categories.filters addresses specs as "specs.<key>", so a nested value
    # would be invisible to every filter and nobody would learn why.
    assert response.status_code == 400


async def test_tags_are_trimmed_and_deduplicated(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    response = await client.post(
        f"{ADMIN}/products",
        headers=headers,
        json=payload(context, tags=["  ახალი  ", "ახალი", "ფასდაკლება", ""]),
    )

    assert response.status_code == 201
    assert response.json()["tags"] == ["ახალი", "ფასდაკლება"]


async def test_a_product_created_in_the_admin_is_found_by_the_storefront_search(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    """The index must be built on the write path, not by a separate script."""
    created = await client.post(
        f"{ADMIN}/products",
        headers=headers,
        json=payload(context, name="ულტრა დამტენი", isActive=True),
    )
    assert created.status_code == 201

    found = await client.get(f"{STORE}/search", params={"q": "დამტენი"})

    assert found.status_code == 200
    slugs = [item["slug"] for item in found.json()]
    assert created.json()["slug"] in slugs


async def test_renaming_a_product_refreshes_the_search_index(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    created = await client.post(
        f"{ADMIN}/products",
        headers=headers,
        json=payload(context, name="ძველი სახელი", isActive=True),
    )
    product_id = created.json()["id"]

    await client.patch(
        f"{ADMIN}/products/{product_id}", headers=headers, json={"name": "ყურსასმენი Pro"}
    )

    found = await client.get(f"{STORE}/search", params={"q": "ყურსასმენი"})
    assert [item["id"] for item in found.json()] == [product_id]

    # The old name must stop matching, or search results would keep pointing at
    # a product that no longer has that name.
    stale = await client.get(f"{STORE}/search", params={"q": "ძველი"})
    assert stale.json() == []


async def test_archiving_hides_the_product_from_the_storefront(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    created = await client.post(
        f"{ADMIN}/products", headers=headers, json=payload(context, isActive=True)
    )
    product_id = created.json()["id"]
    slug = created.json()["slug"]
    assert (await client.get(f"{STORE}/products/{slug}")).status_code == 200

    response = await client.post(f"{ADMIN}/products/{product_id}/archive", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["archivedAt"] is not None
    # Archiving also clears is_active, which is what makes every existing
    # storefront query keep working without a change.
    assert body["isActive"] is False
    assert (await client.get(f"{STORE}/products/{slug}")).status_code == 404


async def test_an_archived_product_cannot_be_activated_directly(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    created = await client.post(f"{ADMIN}/products", headers=headers, json=payload(context))
    product_id = created.json()["id"]
    await client.post(f"{ADMIN}/products/{product_id}/archive", headers=headers)

    response = await client.patch(
        f"{ADMIN}/products/{product_id}", headers=headers, json={"isActive": True}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PRODUCT_ARCHIVED"


async def test_unarchiving_returns_the_product_as_a_draft(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    created = await client.post(
        f"{ADMIN}/products", headers=headers, json=payload(context, isActive=True)
    )
    product_id = created.json()["id"]
    await client.post(f"{ADMIN}/products/{product_id}/archive", headers=headers)

    response = await client.post(f"{ADMIN}/products/{product_id}/unarchive", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["archivedAt"] is None
    # Deliberately not active: republishing untouched prices and stock should be
    # a decision, not a side effect.
    assert body["isActive"] is False


async def test_archived_products_are_hidden_from_the_admin_list_by_default(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    created = await client.post(f"{ADMIN}/products", headers=headers, json=payload(context))
    product_id = created.json()["id"]
    await client.post(f"{ADMIN}/products/{product_id}/archive", headers=headers)

    default = await client.get(f"{ADMIN}/products", headers=headers)
    assert [item["id"] for item in default.json()["items"]] == []

    included = await client.get(
        f"{ADMIN}/products", headers=headers, params={"includeArchived": "true"}
    )
    assert [item["id"] for item in included.json()["items"]] == [product_id]


async def test_duplicating_copies_content_but_not_images_or_stock(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    created = await client.post(
        f"{ADMIN}/products", headers=headers, json=payload(context, sku="ORIG-1", isActive=True)
    )
    source = created.json()

    response = await client.post(f"{ADMIN}/products/{source['id']}/duplicate", headers=headers)

    assert response.status_code == 201
    copy = response.json()
    assert copy["id"] != source["id"]
    assert copy["slug"] == f"{source['slug']}-copy"
    assert copy["sku"] == "ORIG-1-COPY"
    assert copy["specs"] == source["specs"]
    # A copy has no stock and is not live until someone says so.
    assert copy["stock"] == 0
    assert copy["isActive"] is False
    # Images are not copied: two products pointing at one storage object would
    # make deleting either of them ambiguous.
    assert copy["images"] == []


async def test_the_search_filter_matches_name_sku_and_slug(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    await client.post(
        f"{ADMIN}/products",
        headers=headers,
        json=payload(context, name="ხელსაწყო", sku="TOOL-77"),
    )

    by_name = await client.get(f"{ADMIN}/products", headers=headers, params={"q": "ხელსაწყო"})
    by_sku = await client.get(f"{ADMIN}/products", headers=headers, params={"q": "tool-77"})
    by_slug = await client.get(f"{ADMIN}/products", headers=headers, params={"q": "khelsatsqo"})

    assert by_name.json()["total"] == 1
    assert by_sku.json()["total"] == 1
    assert by_slug.json()["total"] == 1


async def test_an_unknown_sort_is_refused_rather_than_interpolated(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.get(
        f"{ADMIN}/products", headers=headers, params={"sort": "price; DROP TABLE products"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNKNOWN_SORT"


async def test_low_stock_filter(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, slug="stocked")
    brand = await make_brand(db, "StockBrand")
    low = await make_product(db, category, brand, slug="low-one", stock=2)
    await make_product(db, category, brand, slug="plenty", stock=50)

    response = await client.get(f"{ADMIN}/products", headers=headers, params={"lowStock": "true"})

    assert [item["id"] for item in response.json()["items"]] == [str(low.id)]
    assert response.json()["items"][0]["stockStatus"] == "low"


async def test_the_list_uses_the_projects_pagination_envelope(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, slug="paged")
    brand = await make_brand(db, "PageBrand")
    for index in range(5):
        await make_product(db, category, brand, slug=f"page-{index}")

    response = await client.get(f"{ADMIN}/products", headers=headers, params={"limit": 2})

    body = response.json()
    # The storefront's shape, not the brief's {items,total,page,page_size}.
    assert set(body) == {"items", "total", "page", "totalPages", "limit"}
    assert (body["total"], body["totalPages"], body["limit"]) == (5, 3, 2)


async def test_a_product_response_never_exposes_the_search_index(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str]
) -> None:
    body = (await client.post(f"{ADMIN}/products", headers=headers, json=payload(context))).json()

    # search_text is an implementation detail; exposing it invites someone to
    # write to it by hand and desynchronise the index.
    assert "searchText" not in body
    assert "search_text" not in body


CUSTOMER = {
    "firstName": "გიორგი",
    "lastName": "ბერიძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
    "email": "giorgi@example.ge",
}


async def test_deleting_a_product_removes_it_and_its_stock_ledger(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str], db: AsyncSession
) -> None:
    created = await client.post(f"{ADMIN}/products", headers=headers, json=payload(context))
    product_id = created.json()["id"]

    response = await client.delete(f"{ADMIN}/products/{product_id}", headers=headers)

    assert response.status_code == 204
    assert (await client.get(f"{ADMIN}/products/{product_id}", headers=headers)).status_code == 404
    assert await db.get(Product, uuid.UUID(product_id)) is None
    # inventory_movements is ON DELETE CASCADE. A product that never sold has no
    # stock history worth keeping once the product itself is gone.
    movements = await db.scalars(
        select(InventoryMovement).where(InventoryMovement.product_id == uuid.UUID(product_id))
    )
    assert list(movements.all()) == []


async def test_a_product_that_has_been_ordered_cannot_be_deleted(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str], db: AsyncSession
) -> None:
    """order_items.product_id is ON DELETE RESTRICT for a reason.

    Deleting a sold product would rewrite what a customer actually bought. The
    409 has to say so clearly enough that the caller reaches for archiving.
    """
    created = await client.post(
        f"{ADMIN}/products", headers=headers, json=payload(context, isActive=True)
    )
    product_id = created.json()["id"]
    await order_service.create_order(
        db,
        items=[(uuid.UUID(product_id), 1)],
        customer=dict(CUSTOMER),
        payment_method="cash",
        user=None,
    )

    response = await client.delete(f"{ADMIN}/products/{product_id}", headers=headers)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "PRODUCT_IN_USE"
    assert error["details"]["ordersCount"] == 1
    assert (await client.get(f"{ADMIN}/products/{product_id}", headers=headers)).status_code == 200
    # Archiving is the way out, and it still works.
    assert (
        await client.post(f"{ADMIN}/products/{product_id}/archive", headers=headers)
    ).status_code == 200


async def test_deleting_an_unknown_product_is_a_404(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.delete(f"{ADMIN}/products/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


async def test_the_audit_row_outlives_the_deleted_product(
    client: httpx.AsyncClient, headers: dict[str, str], context: dict[str, str], db: AsyncSession
) -> None:
    """The product row is gone, so the audit entry has to carry what it was."""
    created = await client.post(
        f"{ADMIN}/products", headers=headers, json=payload(context, sku="GONE-1")
    )
    product_id = created.json()["id"]

    await client.delete(f"{ADMIN}/products/{product_id}", headers=headers)

    entry = await db.scalar(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "product.delete",
            AdminAuditLog.entity_id == product_id,
        )
    )
    assert entry is not None
    assert entry.changes["sku"] == "GONE-1"
    assert entry.changes["slug"] == "iphone-15-pro"
