"""`search_text`-ის ხელახალი გამოთვლა ყველა პროდუქტისთვის.

გაუშვი მაშინ, თუ პროდუქტი ბაზაში დაემატა ან შეიცვალა `import_products.py`-ის
გვერდის ავლით — მაგალითად Supabase-ის Table Editor-იდან. ამის გარეშე პროდუქტი
კატალოგში ჩანს, მაგრამ ძებნა მას ვერ პოულობს.

გაშვება:
    python scripts/reindex_search.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models import Product
from app.db.session import SessionLocal, engine
from app.services.search import build_search_text


async def main() -> None:
    changed = 0
    async with SessionLocal() as db:
        products = (await db.scalars(select(Product))).unique().all()
        for product in products:
            fresh = build_search_text(
                name=product.name,
                brand_name=product.brand.name,
                category_name=product.category.name,
                category_slug=product.category.slug,
                short_description=product.short_description,
                tags=list(product.tags),
                specs=product.specs,
            )
            if fresh != product.search_text:
                product.search_text = fresh
                changed += 1
        await db.commit()

    await engine.dispose()
    print(f"  ✔ reindex: {len(products)} პროდუქტი შემოწმდა, {changed} განახლდა")


if __name__ == "__main__":
    asyncio.run(main())
