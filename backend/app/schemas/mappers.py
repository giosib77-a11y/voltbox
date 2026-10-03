"""ORM-ობიექტების API-სქემებად გადაქცევა.

აქ ითვლება ყველა წარმოებული ველი. მათი გამოთვლა კომპონენტებში ან ORM-ში
განზრახ არ ხდება: ერთი ადგილი ნიშნავს, რომ `discountPercent` ყველგან ერთი და
იმავე წესით ითვლება — იხ. frontend-ის `calcDiscountPercent`.

Names and the description come out in the language the request asked for
(`lang`), never both: a shopper does not download text they will not see.
`lang` has no default on purpose - a caller that forgets it fails mypy instead
of quietly answering an English page in Georgian.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.core.language import Language, localized
from app.db.models import Brand, Category, Product
from app.schemas.catalog import BrandOut, CategoryOut, ProductOut, ProductSuggestionOut


def discount_percent(price: Decimal, old_price: Decimal | None) -> int:
    """(2799, 2499) → 11. ROUND_HALF_UP — Python-ის ნაგულისხმევი banker's rounding
    ლუწ რიცხვებზე ქვევით ამრგვალებს და frontend-ის `Math.round`-ს დაშორდებოდა."""
    if not old_price or old_price <= price:
        return 0
    ratio = (old_price - price) / old_price * 100
    return int(ratio.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def product_to_out(product: Product, *, lang: Language) -> ProductOut:
    percent = discount_percent(product.price, product.old_price)
    return ProductOut(
        id=product.id,
        slug=product.slug,
        name=localized(product.name, product.name_en, lang),
        brand=localized(product.brand.name, product.brand.name_en, lang),
        brand_country=product.brand.country,
        category=product.category.slug,
        short_description=product.short_description,
        description=localized(product.description, product.description_en, lang),
        price=product.price,
        old_price=product.old_price,
        rating=product.rating,
        reviews_count=product.reviews_count,
        stock=product.stock,
        is_new=product.is_new,
        is_featured=product.is_featured,
        images=[image.url for image in sorted(product.images, key=lambda i: i.position)],
        specs=product.specs,
        tags=list(product.tags),
        created_at=product.created_at,
        discount_percent=percent,
        has_discount=percent > 0,
        in_stock=product.stock > 0,
        is_low_stock=0 < product.stock <= product.low_stock_threshold,
    )


def product_to_suggestion(product: Product, *, lang: Language) -> ProductSuggestionOut:
    primary = next(
        (image.url for image in product.images if image.is_primary),
        product.images[0].url if product.images else "",
    )
    return ProductSuggestionOut(
        id=product.id,
        slug=product.slug,
        name=localized(product.name, product.name_en, lang),
        brand=localized(product.brand.name, product.brand.name_en, lang),
        price=product.price,
        images=[primary] if primary else [],
    )


def category_to_out(category: Category, products_count: int, *, lang: Language) -> CategoryOut:
    # There is no English short name. On /en the English name stands in for
    # both, and without one the Georgian short name is kept as it is.
    short_name = category.short_name or category.name
    return CategoryOut(
        id=category.id,
        slug=category.slug,
        name=localized(category.name, category.name_en, lang),
        short_name=localized(short_name, category.name_en, lang),
        description=category.description,
        icon=category.icon,
        parent_id=category.parent_id,
        filters=category.filters,
        products_count=products_count,
    )


def brand_to_out(brand: Brand, products_count: int, *, lang: Language) -> BrandOut:
    return BrandOut(
        id=brand.id,
        slug=brand.slug,
        name=localized(brand.name, brand.name_en, lang),
        country=brand.country,
        products_count=products_count,
    )
