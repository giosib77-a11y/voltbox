"""Admin request/response schemas for categories and brands.

What it does: validates what an administrator may write, and shapes what the
admin UI reads back.
Where it fits: app/api/v1/routes/admin/categories.py and brands.py.
Notes: CategoryFilter mirrors the structure the storefront already reads
(FilterSidebar / paramForFilter). Inventing a different shape here would break
filtering on the live site, so this model is a description of existing data, not
a new design.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.base import ApiModel, ApiRequest

FilterType = Literal["checkbox", "toggle", "swatch"]

MAX_FILTERS_PER_CATEGORY = 20


class CategoryFilter(ApiRequest):
    """One entry of `categories.filters`.

    `key` is either `brand` or `specs.<specKey>`; the `specs.` prefix is what
    ties a filter to a product's `specs` object. `match` marks what counts as
    "on" for a toggle and is a string or a boolean - both appear in live data
    (`"5G"` and `true`).
    """

    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=100)
    type: FilterType
    match: str | bool | None = None

    @field_validator("key")
    @classmethod
    def check_key(cls, value: str) -> str:
        if value == "brand":
            return value
        if not value.startswith("specs."):
            raise ValueError('filter key must be "brand" or start with "specs."')
        spec_key = value[len("specs.") :]
        if not spec_key or not spec_key.replace("_", "").isalnum():
            raise ValueError("spec key must be alphanumeric")
        return value

    @model_validator(mode="after")
    def check_match(self) -> CategoryFilter:
        # `match` only means something for a toggle; allowing it elsewhere would
        # let an author write a value the storefront silently ignores.
        if self.type != "toggle" and self.match is not None:
            raise ValueError('"match" is only valid for a toggle filter')
        if self.type == "toggle" and self.match is None:
            raise ValueError('a toggle filter needs "match"')
        return self


class CategoryCreate(ApiRequest):
    name: str = Field(min_length=1, max_length=150)
    slug: str | None = Field(default=None, max_length=100)
    short_name: str = Field(default="", max_length=150)
    description: str = ""
    icon: str = Field(default="Package", max_length=50)
    parent_id: UUID | None = None
    position: int = Field(default=0, ge=0)
    image_url: str | None = None
    filters: Annotated[list[CategoryFilter], Field(max_length=MAX_FILTERS_PER_CATEGORY)] = Field(
        default_factory=list
    )


class CategoryUpdate(ApiRequest):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    slug: str | None = Field(default=None, max_length=100)
    short_name: str | None = Field(default=None, max_length=150)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=50)
    parent_id: UUID | None = None
    position: int | None = Field(default=None, ge=0)
    image_url: str | None = None
    filters: Annotated[list[CategoryFilter], Field(max_length=MAX_FILTERS_PER_CATEGORY)] | None = (
        None
    )


class CategoryAdminOut(ApiModel):
    id: UUID
    slug: str
    name: str
    short_name: str
    description: str
    icon: str
    parent_id: UUID | None
    position: int
    image_url: str | None
    filters: list[dict[str, object]]
    products_count: int
    children_count: int
    created_at: datetime
    updated_at: datetime


class BrandCreate(ApiRequest):
    name: str = Field(min_length=1, max_length=150)
    slug: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    logo_url: str | None = None


class BrandUpdate(ApiRequest):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    slug: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    logo_url: str | None = None


class BrandAdminOut(ApiModel):
    id: UUID
    slug: str
    name: str
    country: str | None
    logo_url: str | None
    products_count: int
    created_at: datetime
    updated_at: datetime
