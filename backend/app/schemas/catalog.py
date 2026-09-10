"""კატალოგის API-სქემები.

ფორმა frontend-ის კომპონენტებით არის ნაკარნახევი და არა ბაზის სტრუქტურით:
  · `brand` და `category` სტრიქონებია (სახელი / slug), არა ჩალაგებული ობიექტები
  · `images` სტრიქონების მასივია, არა {url, alt, position} ობიექტების
  · წარმოებული ველები (hasDiscount, inStock, ...) ყოველთვის მოდის სერვერიდან
იხ. `../frontend/src/types.js` და
`../frontend/src/components/product/ProductCard.jsx`.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.base import ApiModel


class ProductOut(ApiModel):
    id: UUID
    slug: str
    name: str
    brand: str
    brand_country: str | None
    category: str
    short_description: str
    description: str
    price: Decimal
    old_price: Decimal | None
    rating: Decimal
    reviews_count: int
    stock: int
    is_new: bool
    is_featured: bool
    images: list[str]
    specs: dict[str, Any]
    tags: list[str]
    created_at: datetime

    # --- წარმოებული: ბაზაში არ ინახება, ყოველთვის სერვერზე ითვლება ------------
    discount_percent: int
    has_discount: bool
    in_stock: bool
    is_low_stock: bool


class ProductSuggestionOut(ApiModel):
    """მსუბუქი ვარიანტი header-ის autocomplete-ისთვის.

    `SearchSuggestions.jsx` აჩვენებს: სურათს, სახელს, ბრენდს და ფასს — მეტი
    ველი ზედმეტ ტრაფიკს ნიშნავს.
    """

    id: UUID
    slug: str
    name: str
    brand: str
    price: Decimal
    images: list[str]


class PriceFacet(ApiModel):
    """min/max — მთელი ნაკრების საზღვრები (სლაიდერის დიაპაზონი),
    currentMin/currentMax — მიმდინარე შედეგისა."""

    min: int
    max: int
    current_min: int
    current_max: int


class Facets(ApiModel):
    """⚠️ ფორმა `FilterSidebar.jsx`-ითაა ნაკარნახევი:

        facets.values[config.key] → {"Apple": 12, "Samsung": 5}

    ანუ ობიექტ-რუკა და არა მასივი. გასაღები ფილტრის სრული `key`-ია
    (`brand`, `specs.ram`) — ზუსტად ისე, როგორც `categories.filters`-შია.
    """

    values: dict[str, dict[str, int]] = Field(default_factory=dict)
    price: PriceFacet


class ProductListOut(ApiModel):
    items: list[ProductOut]
    total: int
    page: int
    total_pages: int
    limit: int
    facets: Facets


class CategoryFilterOut(ApiModel):
    key: str
    label: str
    type: str
    match: Any = None
    param: str | None = None
    option_labels: dict[str, str] | None = None


class CategoryOut(ApiModel):
    id: UUID
    slug: str
    name: str
    short_name: str
    description: str
    icon: str
    filters: list[CategoryFilterOut]
    products_count: int


class BrandOut(ApiModel):
    id: UUID
    slug: str
    name: str
    country: str | None
    products_count: int


class HomeSectionsOut(ApiModel):
    new_arrivals: list[ProductOut]
    discounted: list[ProductOut]
    featured: list[ProductOut]
    popular_categories: list[CategoryOut]
