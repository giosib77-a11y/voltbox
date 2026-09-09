"""ძებნის მარშრუტი — header-ის autocomplete-ისთვის."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.catalog import ProductSuggestionOut
from app.schemas.mappers import product_to_suggestion
from app.services import search

router = APIRouter(tags=["search"])


@router.get(
    "/search",
    summary="Search products",
    description=(
        "Lightweight product search for the header autocomplete. "
        "Returns id, name, slug, brand, price and the primary image only."
    ),
    response_model=list[ProductSuggestionOut],
)
async def search_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str, Query(max_length=200, description="Search query")] = "",
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[ProductSuggestionOut]:
    # ქართული ახსნა: ცარიელ query-ზე ბაზას საერთოდ არ ვაწუხებთ — header-ი
    # ველის გასუფთავებისას სწორედ ამას აგზავნის
    if not q.strip():
        return []
    products = await search.search_products(db, q, limit=limit)
    return [product_to_suggestion(p) for p in products]
