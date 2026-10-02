"""The sitemap.

What it does: one XML document listing every page a search engine should know
about - the fixed pages, each category, and each product that is actually on
sale.
Where it fits: mounted outside the versioned API, because a sitemap's URL is
part of the site's contract with a crawler and `/api/v1/sitemap.xml` is not a
place anybody looks.

Why the backend and not the build: the frontend is a static bundle and has no
idea what is in the catalogue. A sitemap generated at build time is a snapshot
that goes stale the first time a product is added, and the whole point of the
file is to be current.

Every page is listed in both languages - Georgian at its own path, English
under /en - and each entry names both versions, with the Georgian as
x-default: the form Google reads hreflang from in a sitemap. The paths must
agree with the storefront's `localizedPath` (frontend/src/i18n/index.js).

Notes: the shop is a separate host from this API, so every URL is built from
SITE_URL rather than from the request. Serving this file under the shop's own
domain - a rewrite on the static host - is what makes a crawler trust it
without extra verification.
"""

from __future__ import annotations

from datetime import datetime
from xml.sax.saxutils import escape

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import Db
from app.db.models import Category, Product

router = APIRouter(tags=["seo"])

#: How often a crawler is told to come back, and how much each page matters
#: relative to the others. Both are hints; the ordering is the honest part.
FIXED_PAGES = [
    ("/", "daily", "1.0"),
    ("/search", "weekly", "0.3"),
    # The footer's information pages - INFO_PAGES in the storefront's
    # src/constants/index.js; tests/test_sitemap.py reads the paths from there.
    ("/delivery", "monthly", "0.4"),
    ("/returns", "monthly", "0.4"),
    ("/privacy", "yearly", "0.2"),
    ("/faq", "monthly", "0.4"),
]

CATEGORY_PRIORITY = "0.8"
PRODUCT_PRIORITY = "0.7"


#: Each language and what it puts in front of a path. Georgian, the default,
#: keeps the bare path - every link shared before English existed still works.
LANGUAGES = (("ka", ""), ("en", "/en"))
DEFAULT_LANGUAGE = "ka"


def _url(path: str) -> str:
    return f"{settings.site_url.rstrip('/')}{path}"


def _localized(path: str, prefix: str) -> str:
    """`/cart` under `/en` is `/en/cart`; the home page is `/en`, not `/en/`."""
    if not prefix:
        return path
    return prefix if path == "/" else f"{prefix}{path}"


def _entries(
    path: str, changefreq: str, priority: str, lastmod: datetime | None = None
) -> list[str]:
    """One <url> per language, each naming every language's version of the page."""
    versions = {language: _url(_localized(path, prefix)) for language, prefix in LANGUAGES}
    alternates = [
        f'    <xhtml:link rel="alternate" hreflang="{language}" href="{escape(href)}"/>'
        for language, href in versions.items()
    ]
    alternates.append(
        '    <xhtml:link rel="alternate" hreflang="x-default" '
        f'href="{escape(versions[DEFAULT_LANGUAGE])}"/>'
    )

    entries = []
    for loc in versions.values():
        parts = [f"    <loc>{escape(loc)}</loc>", *alternates]
        if lastmod is not None:
            parts.append(f"    <lastmod>{lastmod.date().isoformat()}</lastmod>")
        parts.append(f"    <changefreq>{changefreq}</changefreq>")
        parts.append(f"    <priority>{priority}</priority>")
        body = "\n".join(parts)
        entries.append(f"  <url>\n{body}\n  </url>")
    return entries


async def build_sitemap(db: AsyncSession) -> str:
    """The document, as text. Separate from the route so a test can read it."""
    entries = [
        entry for path, freq, priority in FIXED_PAGES for entry in _entries(path, freq, priority)
    ]

    categories = (
        await db.scalars(select(Category).order_by(Category.position, Category.slug))
    ).all()
    # Only what a visitor can actually reach: an archived or switched-off
    # product answers 404 on the storefront, and a sitemap full of 404s is how a
    # site teaches a crawler to trust it less.
    products = (
        await db.scalars(
            select(Product)
            .where(Product.is_active.is_(True), Product.archived_at.is_(None))
            .order_by(Product.slug)
        )
    ).all()

    for category in categories:
        entries += _entries(f"/category/{category.slug}", "weekly", CATEGORY_PRIORITY)
    for product in products:
        entries += _entries(
            f"/product/{product.slug}", "weekly", PRODUCT_PRIORITY, product.updated_at
        )

    joined = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
        ' xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        f"{joined}\n"
        "</urlset>\n"
    )


@router.get("/sitemap.xml", summary="Sitemap", include_in_schema=False)
async def sitemap(db: Db) -> Response:
    return Response(
        content=await build_sitemap(db),
        media_type="application/xml",
        # An hour: long enough that a crawler hitting it repeatedly costs
        # nothing, short enough that a product added today is found today.
        headers={"Cache-Control": "public, max-age=3600"},
    )
