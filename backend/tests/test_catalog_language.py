"""English names on the /en storefront.

What it covers: a category, brand or product with an English name is shown by
it when the request says `lang=en`; without one the Georgian is shown, never a
blank; a request without `lang` - every Georgian page - gets exactly the
Georgian it got before; search finds a product by either name; and the admin
saves both names and reads them back.

The language travels as a query parameter (app/core/language.py), so these
tests ask for it the way the English storefront does.
"""

import httpx
import pytest
from app.db.models import ROLE_ADMIN, Brand, Category, Product
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

STORE = "/api/v1"
ADMIN = "/api/v1/admin"
EN = {"lang": "en"}


@pytest.fixture
async def shop(db: AsyncSession) -> dict[str, object]:
    """One translated product and one untranslated, under a translated category.

    The translated brand is written in Georgian script on purpose: its value in
    the brand filter stays the Georgian name, and only its label is English.
    """
    category = await make_category(db, "headphones", name="ყურსასმენები", name_en="Headphones")
    hoco = await make_brand(db, "ჰოკო", name_en="Hoco")
    apple = await make_brand(db, "Apple")
    translated = await make_product(
        db,
        category,
        hoco,
        slug="earbuds-pro",
        name="უსადენო ყურსასმენი Pro",
        name_en="Wireless Earbuds Pro",
        description_en="Noise cancelling, eight hours a charge.",
        reviews_count=50,
    )
    untranslated = await make_product(
        db, category, apple, slug="airpods", name="ყურსასმენი AirPods", reviews_count=10
    )
    return {
        "category": category,
        "hoco": hoco,
        "translated": translated,
        "untranslated": untranslated,
    }


def _names(items: list[dict[str, object]]) -> dict[object, object]:
    return {item["slug"]: item["name"] for item in items}


# --- English shown on /en ---------------------------------------------------


async def test_an_english_page_gets_the_english_name_and_description(
    client: httpx.AsyncClient, shop: dict[str, object]
) -> None:
    product = await client.get(f"{STORE}/products/earbuds-pro", params=EN)

    assert product.status_code == 200
    body = product.json()
    assert body["name"] == "Wireless Earbuds Pro"
    assert body["description"] == "Noise cancelling, eight hours a charge."
    assert body["brand"] == "Hoco"
    # The same product at the same address: one slug, two languages.
    assert body["slug"] == "earbuds-pro"
    assert body["category"] == "headphones"


async def test_every_catalogue_read_answers_in_english(
    client: httpx.AsyncClient, shop: dict[str, object]
) -> None:
    """Lists, related, by id, the home page and the menu - not just one route."""
    translated = shop["translated"]
    untranslated = shop["untranslated"]
    assert isinstance(translated, Product) and isinstance(untranslated, Product)

    listing = await client.get(f"{STORE}/products", params={"category": "headphones", **EN})
    assert _names(listing.json()["items"])["earbuds-pro"] == "Wireless Earbuds Pro"

    by_id = await client.get(f"{STORE}/products/by-id/{translated.id}", params=EN)
    assert by_id.json()["name"] == "Wireless Earbuds Pro"

    related = await client.get(f"{STORE}/products/{untranslated.id}/related", params=EN)
    assert _names(related.json())["earbuds-pro"] == "Wireless Earbuds Pro"

    home = (await client.get(f"{STORE}/home-sections", params=EN)).json()
    assert _names(home["latest"])["earbuds-pro"] == "Wireless Earbuds Pro"
    assert home["popularCategories"][0]["name"] == "Headphones"

    categories = (await client.get(f"{STORE}/categories", params=EN)).json()
    assert categories[0]["name"] == "Headphones"
    # The menu reads shortName; there is no English one, so the name stands in.
    assert categories[0]["shortName"] == "Headphones"

    brands = {b["slug"]: b["name"] for b in (await client.get(f"{STORE}/brands", params=EN)).json()}
    assert brands["ჰოკო"] == "Hoco"


async def test_the_brand_filter_keeps_its_value_and_shows_the_english_label(
    client: httpx.AsyncClient, shop: dict[str, object]
) -> None:
    """`?brand=ჰოკო` is the same link in both languages; only the label changes."""
    params = {"category": "headphones", **EN}
    facets = (await client.get(f"{STORE}/products", params=params)).json()["facets"]

    assert facets["values"]["brand"] == {"ჰოკო": 1, "Apple": 1}
    assert facets["labels"] == {"brand": {"ჰოკო": "Hoco"}}

    filtered = await client.get(f"{STORE}/products", params={**params, "brand": "ჰოკო"})
    assert list(_names(filtered.json()["items"])) == ["earbuds-pro"]


# --- Georgian when there is no English ---------------------------------------


async def test_an_untranslated_product_shows_its_georgian_on_an_english_page(
    client: httpx.AsyncClient, shop: dict[str, object]
) -> None:
    body = (await client.get(f"{STORE}/products/airpods", params=EN)).json()

    assert body["name"] == "ყურსასმენი AirPods"
    assert body["description"] == "სრული აღწერა"
    assert body["brand"] == "Apple"


async def test_a_blank_english_name_counts_as_none(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, object]
) -> None:
    """A lone space typed into the database by hand must not show as a blank card."""
    untranslated, hoco = shop["untranslated"], shop["hoco"]
    assert isinstance(untranslated, Product) and isinstance(hoco, Brand)
    untranslated.name_en = " "
    untranslated.description_en = "\n"
    hoco.name_en = "  "
    await db.flush()

    body = (await client.get(f"{STORE}/products/airpods", params=EN)).json()

    assert body["name"] == "ყურსასმენი AirPods"
    assert body["description"] == "სრული აღწერა"

    # The brand filter's label is chosen in SQL, so it is held to the same rule.
    listing = (
        await client.get(f"{STORE}/products", params={"category": "headphones", **EN})
    ).json()
    assert _names(listing["items"])["earbuds-pro"] == "Wireless Earbuds Pro"
    assert [item["brand"] for item in listing["items"] if item["slug"] == "earbuds-pro"] == ["ჰოკო"]
    assert listing["facets"]["labels"] == {}


async def test_an_untranslated_category_and_brand_show_their_georgian(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await make_category(db, "cables", name="კაბელები")
    brand = await make_brand(db, "ბრენდი")
    category = await make_category(db, "chargers", name="დამტენები")
    await make_product(db, category, brand, slug="charger", name="დამტენი 20W")

    categories = {
        c["slug"]: (c["name"], c["shortName"])
        for c in (await client.get(f"{STORE}/categories", params=EN)).json()
    }
    assert categories["cables"] == ("კაბელები", "კაბელები")

    product = (await client.get(f"{STORE}/products/charger", params=EN)).json()
    assert product["brand"] == "ბრენდი"

    facets = (await client.get(f"{STORE}/products", params={"category": "chargers", **EN})).json()[
        "facets"
    ]
    assert facets["labels"] == {}


# --- Georgian unaffected ----------------------------------------------------


async def test_a_georgian_page_gets_georgian_even_where_english_exists(
    client: httpx.AsyncClient, shop: dict[str, object]
) -> None:
    """Every Georgian page sends no `lang`, which is how it asked before."""
    product = (await client.get(f"{STORE}/products/earbuds-pro")).json()
    assert product["name"] == "უსადენო ყურსასმენი Pro"
    assert product["description"] == "სრული აღწერა"
    assert product["brand"] == "ჰოკო"

    category = (await client.get(f"{STORE}/categories")).json()[0]
    assert (category["name"], category["shortName"]) == ("ყურსასმენები", "ყურსასმენები")

    listing = (await client.get(f"{STORE}/products", params={"category": "headphones"})).json()
    assert _names(listing["items"])["earbuds-pro"] == "უსადენო ყურსასმენი Pro"
    assert listing["facets"]["labels"] == {}

    suggestions = (await client.get(f"{STORE}/search", params={"q": "wireless"})).json()
    assert [(s["name"], s["brand"]) for s in suggestions] == [("უსადენო ყურსასმენი Pro", "ჰოკო")]


async def test_lang_ka_is_the_same_answer_as_no_lang(
    client: httpx.AsyncClient, shop: dict[str, object]
) -> None:
    for path, params in [
        ("/products/earbuds-pro", {}),
        ("/products", {"category": "headphones"}),
        ("/categories", {}),
        ("/brands", {}),
        ("/home-sections", {}),
        ("/search", {"q": "ყურსასმენი"}),
    ]:
        plain = await client.get(f"{STORE}{path}", params=params)
        explicit = await client.get(f"{STORE}{path}", params={**params, "lang": "ka"})
        assert plain.json() == explicit.json(), path


async def test_an_unknown_language_is_refused_not_guessed(
    client: httpx.AsyncClient, shop: dict[str, object]
) -> None:
    response = await client.get(f"{STORE}/products/earbuds-pro", params={"lang": "de"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_lang_is_never_read_as_a_filter(client: httpx.AsyncClient, db: AsyncSession) -> None:
    """A category may well have a `specs.lang` filter - a keyboard's layout."""
    category = await make_category(
        db, "keyboards", filters=[{"key": "specs.lang", "label": "განლაგება", "type": "checkbox"}]
    )
    brand = await make_brand(db, "Logitech")
    await make_product(db, category, brand, slug="k120", specs={"lang": "ქართული"})

    listing = await client.get(f"{STORE}/products", params={"category": "keyboards", **EN})

    assert list(_names(listing.json()["items"])) == ["k120"]


# --- search -----------------------------------------------------------------


async def test_search_on_an_english_page_finds_by_the_english_name(
    client: httpx.AsyncClient, shop: dict[str, object]
) -> None:
    suggestions = (await client.get(f"{STORE}/search", params={"q": "wireless", **EN})).json()
    assert [s["name"] for s in suggestions] == ["Wireless Earbuds Pro"]

    results = (await client.get(f"{STORE}/products", params={"q": "earbuds", **EN})).json()
    assert list(_names(results["items"]).values()) == ["Wireless Earbuds Pro"]


async def test_search_on_an_english_page_still_finds_by_the_georgian_name(
    client: httpx.AsyncClient, shop: dict[str, object]
) -> None:
    suggestions = (await client.get(f"{STORE}/search", params={"q": "უსადენო", **EN})).json()

    assert [s["name"] for s in suggestions] == ["Wireless Earbuds Pro"]


async def test_a_typo_in_the_english_name_is_still_found(
    client: httpx.AsyncClient, shop: dict[str, object]
) -> None:
    """The typo stage compares against both names, not only the Georgian."""
    suggestions = (await client.get(f"{STORE}/search", params={"q": "earbuts", **EN})).json()

    assert [s["name"] for s in suggestions] == ["Wireless Earbuds Pro"]


async def test_the_english_name_ranks_search_results(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, object]
) -> None:
    """Exact, then prefix, then contains - by the English name as by the Georgian.

    All three match "earbuds", and none of their Georgian names does. Ranked by
    the Georgian name alone they would come out by popularity, which here is
    the exact reverse.
    """
    category, hoco = shop["category"], shop["hoco"]
    assert isinstance(category, Category) and isinstance(hoco, Brand)
    await make_product(
        db,
        category,
        hoco,
        slug="earbuds-lite",
        name="ყურსასმენი Lite",
        name_en="Earbuds Lite",
        reviews_count=5000,
    )
    await make_product(
        db, category, hoco, slug="earbuds", name="ყურსასმენი", name_en="Earbuds", reviews_count=1
    )

    suggestions = (await client.get(f"{STORE}/search", params={"q": "earbuds", **EN})).json()

    assert [s["name"] for s in suggestions] == ["Earbuds", "Earbuds Lite", "Wireless Earbuds Pro"]


# --- the cart ---------------------------------------------------------------


async def test_the_cart_names_its_lines_in_the_page_language(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, object]
) -> None:
    """The merge at every signed-in page load replaces the browser's snapshot."""
    translated = shop["translated"]
    assert isinstance(translated, Product)
    headers = auth_header(await make_user(db, email="cart-en@example.ge"))
    lines = {"items": [{"productId": str(translated.id), "qty": 1}]}

    english = await client.post(f"{STORE}/cart/merge", headers=headers, json=lines, params=EN)
    georgian = await client.post(f"{STORE}/cart/merge", headers=headers, json=lines)

    assert english.json()["items"][0]["snapshot"]["name"] == "Wireless Earbuds Pro"
    assert georgian.json()["items"][0]["snapshot"]["name"] == "უსადენო ყურსასმენი Pro"


# --- the admin saves and reads back both ------------------------------------


@pytest.fixture
async def headers(db: AsyncSession) -> dict[str, str]:
    admin = await make_user(db, email="language-admin@voltbox.ge", role=ROLE_ADMIN)
    return auth_header(admin)


async def test_the_admin_saves_and_reloads_a_products_two_names(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, "speakers")
    brand = await make_brand(db, "JBL")
    created = await client.post(
        f"{ADMIN}/products",
        headers=headers,
        json={
            "name": "პორტატული დინამიკი",
            "nameEn": "Boombox Mini",
            "description": "წყალგამძლე.",
            "descriptionEn": "Waterproof.",
            "categoryId": str(category.id),
            "brandId": str(brand.id),
            "price": "199.00",
            "isActive": True,
        },
    )
    assert created.status_code == 201
    product_id = created.json()["id"]

    reloaded = (await client.get(f"{ADMIN}/products/{product_id}", headers=headers)).json()
    assert (reloaded["name"], reloaded["nameEn"]) == ("პორტატული დინამიკი", "Boombox Mini")
    assert (reloaded["description"], reloaded["descriptionEn"]) == ("წყალგამძლე.", "Waterproof.")

    # A patch of the English name alone: saved, shown, and searchable by it.
    patched = await client.patch(
        f"{ADMIN}/products/{product_id}",
        headers=headers,
        json={"nameEn": "Outdoor Speaker", "descriptionEn": ""},
    )
    assert patched.status_code == 200
    reloaded = (await client.get(f"{ADMIN}/products/{product_id}", headers=headers)).json()
    assert (reloaded["name"], reloaded["nameEn"]) == ("პორტატული დინამიკი", "Outdoor Speaker")
    assert reloaded["descriptionEn"] == ""

    slug = reloaded["slug"]
    shown = (await client.get(f"{STORE}/products/{slug}", params=EN)).json()
    assert (shown["name"], shown["description"]) == ("Outdoor Speaker", "წყალგამძლე.")

    found = (await client.get(f"{STORE}/search", params={"q": "outdoor", **EN})).json()
    assert [s["name"] for s in found] == ["Outdoor Speaker"]
    # The old English name left the index with the patch. Not "portable": typed
    # on a Georgian layout that becomes პორტატული, the Georgian name itself.
    stale = (await client.get(f"{STORE}/search", params={"q": "boombox", **EN})).json()
    assert stale == []


async def test_the_admin_saves_and_reloads_a_category_and_a_brands_english_name(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    category = await client.post(
        f"{ADMIN}/categories", headers=headers, json={"name": "დამტენები", "nameEn": "Chargers"}
    )
    assert category.status_code == 201
    category_id = category.json()["id"]
    reloaded = (await client.get(f"{ADMIN}/categories/{category_id}", headers=headers)).json()
    assert (reloaded["name"], reloaded["nameEn"]) == ("დამტენები", "Chargers")

    await client.patch(
        f"{ADMIN}/categories/{category_id}", headers=headers, json={"nameEn": "Wall Chargers"}
    )
    reloaded = (await client.get(f"{ADMIN}/categories/{category_id}", headers=headers)).json()
    assert (reloaded["name"], reloaded["nameEn"]) == ("დამტენები", "Wall Chargers")

    brand = await client.post(
        f"{ADMIN}/brands", headers=headers, json={"name": "ჰოკო", "nameEn": "Hoco"}
    )
    assert brand.status_code == 201
    brand_id = brand.json()["id"]
    reloaded = (await client.get(f"{ADMIN}/brands/{brand_id}", headers=headers)).json()
    assert (reloaded["name"], reloaded["nameEn"]) == ("ჰოკო", "Hoco")

    await client.patch(f"{ADMIN}/brands/{brand_id}", headers=headers, json={"nameEn": "HOCO"})
    reloaded = (await client.get(f"{ADMIN}/brands/{brand_id}", headers=headers)).json()
    assert (reloaded["name"], reloaded["nameEn"]) == ("ჰოკო", "HOCO")


async def test_the_english_name_is_optional_and_a_null_is_refused(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    """Optional means absent or empty. A null would reach a NOT NULL column."""
    created = await client.post(f"{ADMIN}/brands", headers=headers, json={"name": "Anker"})
    assert created.status_code == 201
    assert created.json()["nameEn"] == ""

    refused = await client.patch(
        f"{ADMIN}/brands/{created.json()['id']}", headers=headers, json={"nameEn": None}
    )
    assert refused.status_code == 400
    assert refused.json()["error"]["details"][0]["field"] == "nameEn"
