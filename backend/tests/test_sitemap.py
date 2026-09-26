"""The sitemap.

What it covers: that the document lists what a visitor can reach and nothing
else. A sitemap is a promise - every URL in it is a page the site says is worth
crawling - and the two ways to break that promise are listing pages that answer
404 and leaving out the ones that matter.

The archived-product case is the one worth pinning. Archiving is how a shop
retires a product without deleting what people bought, and the storefront
answers 404 for it; a sitemap that still advertised it would hand a crawler a
list of dead links from the shop's own mouth.
"""

import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from app.core.config import settings
from app.db.models import Product
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_brand, make_category, make_product

SITE = "https://voltbox.test"


@pytest.fixture(autouse=True)
def site_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "site_url", SITE)


async def _catalogue(db: AsyncSession) -> dict[str, Product]:
    category = await make_category(db, slug="phones")
    brand = await make_brand(db, "Samsung")
    products = {
        "live": await make_product(db, category, brand, slug="live-one"),
        "hidden": await make_product(db, category, brand, slug="hidden-one"),
        "archived": await make_product(db, category, brand, slug="archived-one"),
    }
    products["hidden"].is_active = False
    products["archived"].archived_at = datetime.now(UTC)
    products["archived"].is_active = False
    await db.flush()
    return products


async def test_it_is_served_as_xml(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await _catalogue(db)

    response = await client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert response.text.startswith('<?xml version="1.0" encoding="UTF-8"?>')


async def test_a_crawler_is_told_to_come_back(client: httpx.AsyncClient) -> None:
    """Without this a crawler re-downloads the whole file on every visit."""
    response = await client.get("/sitemap.xml")

    assert "max-age" in response.headers.get("cache-control", "")


async def test_it_lists_the_pages_a_visitor_can_reach(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await _catalogue(db)

    body = (await client.get("/sitemap.xml")).text

    assert f"<loc>{SITE}/</loc>" in body
    assert f"<loc>{SITE}/category/phones</loc>" in body
    assert f"<loc>{SITE}/product/live-one</loc>" in body


def _info_page_paths() -> list[str]:
    """The paths of the footer's information pages, as the storefront routes them."""
    constants = (
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "constants" / "index.js"
    ).read_text(encoding="utf-8")
    block = re.search(r"export const INFO_PAGES = \{(.*?)\n\};", constants, re.S)
    assert block, "INFO_PAGES moved; this test needs updating"
    return re.findall(r"path: '([^']+)'", block.group(1))


async def test_it_lists_the_footer_information_pages(client: httpx.AsyncClient) -> None:
    # Read from the storefront, so renaming a page there fails here rather than
    # leaving the sitemap pointing a crawler at a 404.
    paths = _info_page_paths()
    assert len(paths) == 4, paths

    body = (await client.get("/sitemap.xml")).text

    for path in paths:
        assert f"<loc>{SITE}{path}</loc>" in body, path


async def test_it_leaves_out_what_answers_404(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await _catalogue(db)

    body = (await client.get("/sitemap.xml")).text

    assert "hidden-one" not in body, "a switched-off product is not on the storefront"
    assert "archived-one" not in body, "an archived product answers 404"


async def test_it_never_advertises_a_page_behind_a_login(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await _catalogue(db)

    body = (await client.get("/sitemap.xml")).text

    for path in ("/admin", "/account", "/checkout", "/cart"):
        assert f"{SITE}{path}" not in body, path


async def test_every_url_is_absolute_and_on_the_shop(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """The API is a different host from the shop, so a URL built from the
    request would point a crawler at the API and every link would 404."""
    await _catalogue(db)

    body = (await client.get("/sitemap.xml")).text

    locations = [
        line.split("<loc>")[1].split("</loc>")[0] for line in body.splitlines() if "<loc>" in line
    ]
    assert locations
    assert all(location.startswith(f"{SITE}/") for location in locations), locations


async def test_a_product_carries_the_date_it_last_changed(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    products = await _catalogue(db)

    body = (await client.get("/sitemap.xml")).text

    assert f"<lastmod>{products['live'].updated_at.date().isoformat()}</lastmod>" in body


async def test_a_slug_with_a_character_xml_cares_about_is_escaped(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """A raw & in a URL makes the whole document unparseable, and a crawler
    that cannot parse it ignores every entry, not just the broken one."""
    category = await make_category(db, slug="phones")
    brand = await make_brand(db, "Samsung")
    product = await make_product(db, category, brand, slug="a-and-b")
    product.slug = "a&b"
    await db.flush()

    body = (await client.get("/sitemap.xml")).text

    assert "a&amp;b" in body
    assert "<loc>https://voltbox.test/product/a&b</loc>" not in body
