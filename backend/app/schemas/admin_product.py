"""Admin request/response schemas for products.

What it does: defines exactly which product fields an administrator may write,
and what the admin list and detail views read back.
Where it fits: app/api/v1/routes/admin/products.py.
Notes: stock is create-only. After creation it moves only through the inventory
endpoints, so every change lands in the ledger. rating, reviews_count,
search_text and archived_at are never writable here - the first two have no
source to recompute from, the third is derived, and the fourth is set by the
archive action so the two cannot drift apart.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.base import ApiModel, ApiRequest

MAX_SPEC_KEYS = 40
MAX_SPEC_KEY_LENGTH = 40
MAX_SPEC_VALUE_LENGTH = 200
MAX_TAGS = 30
MAX_TAG_LENGTH = 50

SpecValue = str | int | float | bool


def _clean_specs(value: dict[str, Any] | None) -> dict[str, SpecValue]:
    """A flat object with trimmed keys and scalar values.

    Nested objects are rejected rather than flattened: `categories.filters`
    addresses specs as `specs.<key>`, so a nested value would be invisible to
    every filter and the author would never learn why.
    """
    if not value:
        return {}
    if len(value) > MAX_SPEC_KEYS:
        raise ValueError(f"At most {MAX_SPEC_KEYS} specifications")

    cleaned: dict[str, SpecValue] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not key:
            raise ValueError("Specification keys cannot be empty")
        if len(key) > MAX_SPEC_KEY_LENGTH:
            raise ValueError(f'Specification key "{key}" is too long')
        if isinstance(raw_value, dict | list):
            raise ValueError(f'Specification "{key}" must be a single value, not a list or object')
        if isinstance(raw_value, str):
            trimmed = raw_value.strip()
            if len(trimmed) > MAX_SPEC_VALUE_LENGTH:
                raise ValueError(f'Specification "{key}" is too long')
            cleaned[key] = trimmed
        elif isinstance(raw_value, bool | int | float):
            cleaned[key] = raw_value
        elif raw_value is None:
            continue
        else:
            raise ValueError(f'Specification "{key}" has an unsupported type')
    return cleaned


def _clean_tags(value: list[str] | None) -> list[str]:
    """Trimmed, de-duplicated, order preserved."""
    if not value:
        return []
    seen: set[str] = set()
    tags: list[str] = []
    for raw in value:
        tag = str(raw).strip()
        if not tag:
            continue
        if len(tag) > MAX_TAG_LENGTH:
            raise ValueError(f'Tag "{tag}" is too long')
        lowered = tag.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        tags.append(tag)
    if len(tags) > MAX_TAGS:
        raise ValueError(f"At most {MAX_TAGS} tags")
    return tags


class ProductCreate(ApiRequest):
    name: str = Field(min_length=1, max_length=300)
    slug: str | None = Field(default=None, max_length=200)
    sku: str | None = Field(default=None, max_length=64)
    category_id: UUID
    brand_id: UUID
    price: Decimal = Field(ge=0, decimal_places=2, max_digits=12)
    old_price: Decimal | None = Field(default=None, ge=0, decimal_places=2, max_digits=12)
    short_description: str = ""
    description: str = ""
    specs: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    low_stock_threshold: int = Field(default=3, ge=0)
    # Create-only. Afterwards stock moves through the inventory endpoints so
    # every change is recorded in inventory_movements.
    stock: int = Field(default=0, ge=0)
    is_active: bool = False
    is_featured: bool = False
    is_new: bool = False

    @field_validator("specs")
    @classmethod
    def check_specs(cls, value: dict[str, Any]) -> dict[str, SpecValue]:
        return _clean_specs(value)

    @field_validator("tags")
    @classmethod
    def check_tags(cls, value: list[str]) -> list[str]:
        return _clean_tags(value)

    @model_validator(mode="after")
    def check_prices(self) -> ProductCreate:
        # Mirrors the old_price_above_price CHECK constraint, so the author gets
        # a field-level message instead of a database error.
        if self.old_price is not None and self.old_price <= self.price:
            raise ValueError("The old price must be higher than the current price")
        return self


class ProductUpdate(ApiRequest):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    slug: str | None = Field(default=None, max_length=200)
    sku: str | None = Field(default=None, max_length=64)
    category_id: UUID | None = None
    brand_id: UUID | None = None
    price: Decimal | None = Field(default=None, ge=0, decimal_places=2, max_digits=12)
    old_price: Decimal | None = Field(default=None, ge=0, decimal_places=2, max_digits=12)
    short_description: str | None = None
    description: str | None = None
    specs: dict[str, Any] | None = None
    tags: list[str] | None = None
    low_stock_threshold: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    is_featured: bool | None = None
    is_new: bool | None = None

    @field_validator("specs")
    @classmethod
    def check_specs(cls, value: dict[str, Any] | None) -> dict[str, SpecValue] | None:
        # None means "not supplied" in a PATCH; {} means "clear them".
        return None if value is None else _clean_specs(value)

    @field_validator("tags")
    @classmethod
    def check_tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_tags(value)

    @model_validator(mode="after")
    def check_prices(self) -> ProductUpdate:
        # Only checkable here when both arrive together; when just one is sent,
        # the service compares against the stored value.
        if self.old_price is not None and self.price is not None and self.old_price <= self.price:
            raise ValueError("The old price must be higher than the current price")
        return self


class ProductImageOut(ApiModel):
    id: UUID
    url: str
    alt: str
    position: int
    is_primary: bool


class ProductAdminOut(ApiModel):
    id: UUID
    slug: str
    sku: str | None
    name: str
    short_description: str
    description: str
    category_id: UUID
    category_name: str
    brand_id: UUID
    brand_name: str
    price: Decimal
    old_price: Decimal | None
    stock: int
    low_stock_threshold: int
    stock_status: Literal["ok", "low", "out"]
    specs: dict[str, Any]
    tags: list[str]
    rating: Decimal
    reviews_count: int
    is_active: bool
    is_featured: bool
    is_new: bool
    archived_at: datetime | None
    images: list[ProductImageOut]
    created_at: datetime
    updated_at: datetime


class ProductListItem(ApiModel):
    """The row shape of the products table - no description, no full specs."""

    id: UUID
    slug: str
    sku: str | None
    name: str
    category_name: str
    brand_name: str
    price: Decimal
    old_price: Decimal | None
    stock: int
    low_stock_threshold: int
    stock_status: Literal["ok", "low", "out"]
    is_active: bool
    is_featured: bool
    is_new: bool
    archived_at: datetime | None
    primary_image: str | None
    created_at: datetime


class ProductPage(ApiModel):
    """Matches the storefront's pagination envelope: items/total/page/totalPages/limit."""

    items: list[ProductListItem]
    total: int
    page: int
    total_pages: int
    limit: int


class StockAdjustRequest(ApiRequest):
    change: Annotated[int, Field(description="Positive adds stock, negative removes it")]
    reason: str = Field(max_length=32)
    note: str | None = Field(default=None, max_length=500)
