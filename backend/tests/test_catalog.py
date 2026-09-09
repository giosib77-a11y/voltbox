"""Phase 2 — კატალოგის წაკითხვების ტესტები."""

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_brand, make_category, make_product


@pytest.fixture
async def catalog(db: AsyncSession) -> dict[str, object]:
    """სამი ტელეფონი, ორი ბრენდი — ყველა შემდეგი მტკიცება ამ ნაკრებს ეყრდნობა."""
    phones = await make_category(db, "phones")
    apple = await make_brand(db, "Apple", "აშშ")
    samsung = await make_brand(db, "Samsung", "სამხრეთ კორეა")

    cheap = await make_product(
        db,
        phones,
        samsung,
        slug="a15",
        name="Galaxy A15",
        price="649.00",
        specs={"ram": "6 GB", "network": "4G", "color": "შავი"},
        rating="4.0",
        reviews_count=300,
        created_at=datetime(2025, 10, 1, tzinfo=UTC),
    )
    mid = await make_product(
        db,
        phones,
        apple,
        slug="iphone-15",
        name="iPhone 15",
        price="2899.00",
        old_price="3199.00",
        specs={"ram": "6 GB", "network": "5G", "color": "თეთრი"},
        rating="4.8",
        reviews_count=200,
        is_featured=True,
        created_at=datetime(2026, 3, 1, tzinfo=UTC),
    )
    sold_out = await make_product(
        db,
        phones,
        samsung,
        slug="s24-ultra",
        name="Galaxy S24 Ultra",
        price="4299.00",
        stock=0,
        specs={"ram": "12 GB", "network": "5G", "color": "ნაცრისფერი"},
        rating="4.9",
        reviews_count=150,
        is_new=True,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    return {"cheap": cheap, "mid": mid, "sold_out": sold_out}


async def test_list_returns_the_envelope_the_frontend_expects(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (await client.get("/api/v1/products", params={"category": "phones"})).json()

    assert set(body) == {"items", "total", "page", "totalPages", "limit", "facets"}
    assert body["total"] == 3
    assert body["totalPages"] == 1


async def test_derived_fields_are_computed_server_side(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (await client.get("/api/v1/products/iphone-15")).json()

    # (3199 - 2899) / 3199 = 9.38% → 9
    assert body["discountPercent"] == 9
    assert body["hasDiscount"] is True
    assert body["inStock"] is True
    assert body["isLowStock"] is False
    assert body["brandCountry"] == "აშშ"


async def test_out_of_stock_product_reports_no_stock(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (await client.get("/api/v1/products/s24-ultra")).json()

    assert body["inStock"] is False
    assert body["hasDiscount"] is False
    assert body["discountPercent"] == 0


async def test_brand_filter_narrows_results(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (
        await client.get("/api/v1/products", params={"category": "phones", "brand": "Samsung"})
    ).json()

    assert body["total"] == 2
    assert {item["brand"] for item in body["items"]} == {"Samsung"}


async def test_multiple_brands_are_comma_separated(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (
        await client.get(
            "/api/v1/products", params={"category": "phones", "brand": "Samsung,Apple"}
        )
    ).json()

    assert body["total"] == 3


async def test_spec_filter_uses_the_short_param_name(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    # frontend URL-ში `specs.ram` პარამეტრად `ram`-ად იწერება
    body = (
        await client.get("/api/v1/products", params={"category": "phones", "ram": "6 GB"})
    ).json()

    assert body["total"] == 2


async def test_toggle_filter_uses_the_configured_match_value(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    # `network=1` ნიშნავს specs.network == "5G" (კონფიგის `match`)
    body = (
        await client.get("/api/v1/products", params={"category": "phones", "network": "1"})
    ).json()

    assert body["total"] == 2


async def test_price_range_uses_dash_format(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (
        await client.get("/api/v1/products", params={"category": "phones", "price": "600-3000"})
    ).json()

    assert body["total"] == 2


async def test_facet_counts_ignore_their_own_filter(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    """ბრენდის არჩევისას ბრენდების სია არ უნდა დაიშალოს ერთ ჩანაწერამდე —
    თორემ მომხმარებელი ვეღარ ხედავს, რას მიიღებდა სხვა არჩევანით."""
    body = (
        await client.get("/api/v1/products", params={"category": "phones", "brand": "Samsung"})
    ).json()

    assert body["facets"]["values"]["brand"] == {"Apple": 1, "Samsung": 2}


async def test_facet_counts_respect_other_filters(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (
        await client.get("/api/v1/products", params={"category": "phones", "ram": "6 GB"})
    ).json()

    assert body["facets"]["values"]["brand"] == {"Apple": 1, "Samsung": 1}


async def test_facets_are_keyed_by_full_filter_key(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    # FilterSidebar `facets.values[config.key]`-ს კითხულობს, სადაც key = "specs.ram"
    body = (await client.get("/api/v1/products", params={"category": "phones"})).json()

    assert "specs.ram" in body["facets"]["values"]
    assert body["facets"]["values"]["specs.ram"] == {"12 GB": 1, "6 GB": 2}


async def test_price_facet_separates_bounds_from_current_range(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (
        await client.get("/api/v1/products", params={"category": "phones", "price": "600-3000"})
    ).json()
    price = body["facets"]["price"]

    # min/max — სლაიდერის საზღვრები (ფასის ფილტრის გარეშე)
    assert (price["min"], price["max"]) == (649, 4299)
    # current* — მიმდინარე შედეგი
    assert (price["currentMin"], price["currentMax"]) == (649, 2899)


async def test_out_of_stock_products_are_listed_last(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (
        await client.get("/api/v1/products", params={"category": "phones", "sort": "price_desc"})
    ).json()

    # S24 Ultra ყველაზე ძვირია, მაგრამ მარაგში არ არის → ბოლოში
    assert body["items"][-1]["slug"] == "s24-ultra"


async def test_sorting_by_price_ascending(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (
        await client.get("/api/v1/products", params={"category": "phones", "sort": "price_asc"})
    ).json()

    assert [item["slug"] for item in body["items"]] == ["a15", "iphone-15", "s24-ultra"]


async def test_sorting_by_newest(client: httpx.AsyncClient, catalog: dict[str, object]) -> None:
    body = (
        await client.get("/api/v1/products", params={"category": "phones", "sort": "newest"})
    ).json()

    assert body["items"][0]["slug"] == "iphone-15"  # 2026-03, S24 Ultra მარაგშია არ არის


async def test_pagination_splits_results(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (
        await client.get("/api/v1/products", params={"category": "phones", "limit": 2, "page": 2})
    ).json()

    assert body["page"] == 2
    assert body["totalPages"] == 2
    assert len(body["items"]) == 1


async def test_limit_above_maximum_is_rejected_not_clamped(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    """ჩუმი clamp კლიენტს აფიქრებინებს, რომ 500 ჩანაწერი მიიღო."""
    response = await client.get("/api/v1/products", params={"limit": 500})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_unknown_product_slug_returns_a_stable_error_code(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/products/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


async def test_related_excludes_the_product_itself(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    product = catalog["mid"]
    body = (await client.get(f"/api/v1/products/{product.id}/related")).json()  # type: ignore[attr-defined]

    assert all(item["slug"] != "iphone-15" for item in body)
    assert len(body) == 2


async def test_categories_include_the_filter_configuration(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    """FilterSidebar სრულად ამ კონფიგზეა აგებული — მის გარეშე ფილტრები ცარიელია."""
    body = (await client.get("/api/v1/categories")).json()

    phones = next(c for c in body if c["slug"] == "phones")
    assert phones["productsCount"] == 3
    assert phones["icon"] == "Smartphone"
    keys = [f["key"] for f in phones["filters"]]
    assert keys == ["brand", "specs.ram", "specs.network", "specs.color"]
    toggle = next(f for f in phones["filters"] if f["type"] == "toggle")
    assert toggle["match"] == "5G"


async def test_brands_include_country_and_counts(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (await client.get("/api/v1/brands")).json()

    samsung = next(b for b in body if b["name"] == "Samsung")
    assert samsung["country"] == "სამხრეთ კორეა"
    assert samsung["productsCount"] == 2


async def test_home_sections_returns_all_four_groups(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (await client.get("/api/v1/home-sections")).json()

    assert set(body) == {"newArrivals", "discounted", "featured", "popularCategories"}
    assert [p["slug"] for p in body["newArrivals"]] == ["s24-ultra"]
    assert [p["slug"] for p in body["discounted"]] == ["iphone-15"]
    assert [p["slug"] for p in body["featured"]] == ["iphone-15"]


async def test_search_falls_back_to_global_facets(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    """ძებნის შედეგი კატეგორიათაშორისია — specs-ის ფილტრები აზრს კარგავს."""
    body = (await client.get("/api/v1/products", params={"q": "galaxy"})).json()

    assert body["total"] == 2
    assert set(body["facets"]["values"]) == {"category", "brand"}


async def test_all_response_keys_are_camel_case(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    body = (await client.get("/api/v1/products/iphone-15")).json()

    assert "_" not in "".join(body.keys())
    assert "shortDescription" in body
    assert "reviewsCount" in body


async def test_filters_accept_both_the_short_and_the_full_key(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    """URL-ი მოკლე სახელს აზიარებს (`ram`), httpApi კი სრულს (`specs.ram`).

    ორივე უნდა მუშაობდეს — წინააღმდეგ შემთხვევაში ფილტრი ჩუმად იკარგება და
    კლიენტი ფიქრობს, რომ გაფილტრული სია მიიღო.
    """
    short = await client.get("/api/v1/products", params={"category": "phones", "ram": "6 GB"})
    full = await client.get("/api/v1/products", params={"category": "phones", "specs.ram": "6 GB"})

    assert short.json()["total"] == full.json()["total"] == 2


async def test_toggle_accepts_both_one_and_true(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    one = await client.get("/api/v1/products", params={"category": "phones", "network": "1"})
    true = await client.get(
        "/api/v1/products", params={"category": "phones", "specs.network": "true"}
    )

    assert one.json()["total"] == true.json()["total"] == 2


async def test_price_accepts_comma_as_well_as_dash(
    client: httpx.AsyncClient, catalog: dict[str, object]
) -> None:
    # frontend-ის URL-ი დეფისს იყენებს, httpApi-ის სერიალიზატორი — მძიმეს
    dash = await client.get("/api/v1/products", params={"category": "phones", "price": "600-3000"})
    comma = await client.get("/api/v1/products", params={"category": "phones", "price": "600,3000"})

    assert dash.json()["total"] == comma.json()["total"] == 2
