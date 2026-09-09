"""პროდუქტების მარშრუტები — თხელი: ვალიდაცია, სერვისი, response model."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError
from app.core.pagination import total_pages
from app.db.session import get_db
from app.schemas.catalog import ProductListOut, ProductOut
from app.schemas.mappers import product_to_out
from app.services import catalog

router = APIRouter(prefix="/products", tags=["products"])

# ეს პარამეტრები ცალკე მუშავდება; დანარჩენი ყველა query param ფილტრად ითვლება
# და `categories.filters` კონფიგის მიხედვით იხსნება
RESERVED_PARAMS = frozenset({"page", "limit", "sort", "q"})


def _filter_params(request: Request) -> dict[str, str]:
    return {
        key: value
        for key, value in request.query_params.items()
        if key not in RESERVED_PARAMS and value != ""
    }


@router.get(
    "",
    summary="List products",
    description=(
        "Paginated product list with filters, sorting and facet counts. "
        "Any query parameter that is not page/limit/sort/q is treated as a filter "
        "and resolved against the category filter configuration."
    ),
    response_model=ProductListOut,
)
async def list_products(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.default_page_size,
    sort: Annotated[str, Query()] = catalog.DEFAULT_SORT,
    q: Annotated[str, Query(max_length=200)] = "",
) -> ProductListOut:
    # ქართული ახსნა: ფილტრები წინასწარ არ არის ჩამოთვლილი, რადგან მათი ნაკრები
    # კატეგორიაზეა დამოკიდებული და ბაზიდან იკითხება — ამიტომ ნედლ query-ს ვიღებთ
    # და სერვისს გადავცემთ. `sort`-ის უცნობი მნიშვნელობა ჩუმად default-ზე ვარდება,
    # რადგან ეს კლიენტის შეცდომა არაა — ბმული შეიძლება ძველი ვერსიიდან იყოს.
    result = await catalog.list_products(
        db,
        query_params=_filter_params(request),
        sort=sort,
        page=page,
        limit=limit,
        search_term=q,
    )

    return ProductListOut(
        items=[product_to_out(p) for p in result["items"]],
        total=result["total"],
        page=page,
        total_pages=total_pages(result["total"], limit),
        limit=limit,
        facets=result["facets"],
    )


@router.get("/by-id/{product_id}", summary="Get a product by id", response_model=ProductOut)
async def get_product_by_id(
    product_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> ProductOut:
    product = await catalog.get_by_id(db, product_id)
    if product is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
    return product_to_out(product)


@router.get("/{slug}", summary="Get a product by slug", response_model=ProductOut)
async def get_product(slug: str, db: Annotated[AsyncSession, Depends(get_db)]) -> ProductOut:
    product = await catalog.get_by_slug(db, slug)
    if product is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
    return product_to_out(product)


@router.get(
    "/{product_id}/related",
    summary="Related products",
    response_model=list[ProductOut],
)
async def get_related(
    product_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=24)] = 8,
) -> list[ProductOut]:
    product = await catalog.get_by_id(db, product_id)
    if product is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
    return [product_to_out(p) for p in await catalog.get_related(db, product, limit)]
