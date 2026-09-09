"""კატეგორიების, ბრენდებისა და მთავარი გვერდის მარშრუტები."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.catalog import BrandOut, CategoryOut, HomeSectionsOut
from app.schemas.mappers import brand_to_out, category_to_out, product_to_out
from app.services import catalog

router = APIRouter(tags=["catalog"])


@router.get(
    "/categories",
    summary="List categories",
    description="Categories with product counts and their filter configuration.",
    response_model=list[CategoryOut],
)
async def list_categories(db: Annotated[AsyncSession, Depends(get_db)]) -> list[CategoryOut]:
    # ქართული ახსნა: `filters` კონფიგი აქვე მიდის — frontend-ის FilterSidebar
    # მთლიანად მასზეა აგებული და ცალკე გამოძახება ზედმეტი round-trip იქნებოდა
    return [category_to_out(c, count) for c, count in await catalog.list_categories(db)]


@router.get(
    "/brands",
    summary="List brands",
    description="Brands with product counts.",
    response_model=list[BrandOut],
)
async def list_brands(db: Annotated[AsyncSession, Depends(get_db)]) -> list[BrandOut]:
    return [brand_to_out(b, count) for b, count in await catalog.list_brands(db)]


@router.get(
    "/home-sections",
    summary="Home page sections",
    description="New arrivals, discounted, featured products and popular categories.",
    response_model=HomeSectionsOut,
)
async def home_sections(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=24)] = 8,
) -> HomeSectionsOut:
    sections = await catalog.home_sections(db, limit)
    return HomeSectionsOut(
        new_arrivals=[product_to_out(p) for p in sections["new_arrivals"]],
        discounted=[product_to_out(p) for p in sections["discounted"]],
        featured=[product_to_out(p) for p in sections["featured"]],
        popular_categories=[
            category_to_out(c, count) for c, count in sections["popular_categories"]
        ],
    )
