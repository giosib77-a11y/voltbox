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
]

CATEGORY_PRIORITY = "0.8"
PRODUCT_PRIORITY = "0.7"


def _url(path: str) -> str:
    return f"{settings.site_url.rstrip('/')}{path}"


def _entry(loc: str, changefreq: str, priority: str, lastmod: datetime | None = None) -> str:
    parts = [f"    <loc>{escape(loc)}</loc>"]
    if lastmod is not None:
        parts.append(f"    <lastmod>{lastmod.date().isoformat()}</lastmod>")
    parts.append(f"    <changefreq>{changefreq}</changefreq>")
    parts.append(f"    <priority>{priority}</priority>")
    body = "\n".join(parts)
    return f"  <url>\n{body}\n  </url>"


async def build_sitemap(db: AsyncSession) -> str:
    """The document, as text. Separate from the route so a test can read it."""
    entries = [_entry(_url(path), freq, priority) for path, freq, priority in FIXED_PAGES]

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

    entries += [
        _entry(_url(f"/category/{category.slug}"), "weekly", CATEGORY_PRIORITY)
        for category in categories
    ]
    entries += [
        _entry(_url(f"/product/{product.slug}"), "weekly", PRODUCT_PRIORITY, product.updated_at)
        for product in products
    ]

    joined = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
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
