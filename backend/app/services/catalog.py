"""კატალოგის ბიზნეს-ლოგიკა: ფილტრაცია, სორტი, პაგინაცია, facet-ები.

ფილტრები data-driven-ია — რომელი პარამეტრი რომელ ველს ეხება, `categories.filters`
კონფიგიდან იკითხება (იგივე კონფიგი, რომელსაც frontend-ის FilterSidebar კითხულობს).
ახალი ფილტრის დამატება არც აქ და არც frontend-ში კოდის ცვლილებას არ საჭიროებს.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import settings
from app.db.models import Brand, Category, Product

# ძებნის გვერდზე კატეგორია აღარაა ერთი — ფილტრებად კატეგორია და ბრენდი გვრჩება
GLOBAL_FILTERS: list[dict[str, Any]] = [
    {"key": "category", "label": "კატეგორია", "type": "checkbox"},
    {"key": "brand", "label": "ბრენდი", "type": "checkbox"},
]

SORTABLE: dict[str, tuple[ColumnElement[Any], ...]] = {
    "price_asc": (Product.price.asc(),),
    "price_desc": (Product.price.desc(),),
    "newest": (Product.created_at.desc(),),
    "rating": (Product.rating.desc(), Product.reviews_count.desc()),
    # პოპულარობა: რეიტინგი × ლოგარითმული წონა შეფასებების რაოდენობაზე —
    # სუფთა რეიტინგი ერთ-შეფასებიან პროდუქტს წინ წამოსწევდა
    "popular": ((Product.rating * func.log(10, Product.reviews_count + 10)).desc(),),
}
DEFAULT_SORT = "popular"


def param_for(filter_config: dict[str, Any]) -> str:
    """`specs.ram` → `ram`. იგივე წესი, რაც frontend-ის `paramForFilter`-ში."""
    param = filter_config.get("param")
    if isinstance(param, str) and param:
        return param
    return str(filter_config["key"]).split(".")[-1]


def _column_for(key: str) -> Any:
    """ფილტრის key-ს ბაზის გამოსახულებად აქცევს.

    `specs.*` → jsonb-ის ტექსტური მნიშვნელობა; `brand`/`category` → ჩალაგებული
    ცხრილის სახელი/slug.
    """
    if key.startswith("specs."):
        return Product.specs[key.split(".", 1)[1]].astext
    if key == "brand":
        return Brand.name
    if key == "category":
        return Category.slug
    return getattr(Product, key)


def _condition(filter_config: dict[str, Any], raw: str) -> Any | None:
    """ერთი ფილტრის პირობა. `None` ნიშნავს „უგულებელყავი“."""
    key = str(filter_config["key"])
    column = _column_for(key)

    if filter_config.get("type") == "toggle":
        if raw not in {"1", "true"}:
            return None
        # ჩართულის მნიშვნელობა კონფიგიდან: 5G-ს `match: "5G"` აქვს,
        # ლოგიკურ ველებს კი `match: true` → jsonb-ში "true" სტრიქონია
        match = filter_config.get("match", True)
        return column == ("true" if match is True else str(match))

    values = [v.strip() for v in raw.split(",") if v.strip()]
    if not values:
        return None
    return column.in_(values)


def _price_condition(raw: str) -> Any | None:
    """`price=100-500` — frontend-ის URL-ის ფორმატი."""
    parts = raw.replace(",", "-").split("-")
    if len(parts) != 2:
        return None
    try:
        low, high = Decimal(parts[0]), Decimal(parts[1])
    except (ValueError, ArithmeticError):
        return None
    if high < low:
        return None
    return and_(Product.price >= low, Product.price <= high)


async def resolve_filter_config(
    db: AsyncSession, category_slugs: list[str], has_query: bool
) -> list[dict[str, Any]]:
    """რომელი ფილტრების ნაკრები მოქმედებს ამ მოთხოვნაზე.

    ერთი კატეგორია და ძებნის გარეშე → ამ კატეგორიის კონფიგი (specs-ის ჩათვლით).
    ყველა სხვა შემთხვევაში (ძებნა, რამდენიმე კატეგორია) შედეგი კატეგორიათაშორისია
    და specs-ის ფილტრები აზრს კარგავს — გვრჩება კატეგორია + ბრენდი.
    """
    if has_query or len(category_slugs) != 1:
        return GLOBAL_FILTERS

    category = await db.scalar(select(Category).where(Category.slug == category_slugs[0]))
    if category is None:
        return GLOBAL_FILTERS
    return list(category.filters) or GLOBAL_FILTERS


def _base_query() -> Select[tuple[Product]]:
    return (
        select(Product)
        .join(Brand, Product.brand_id == Brand.id)
        .join(Category, Product.category_id == Category.id)
        .where(Product.is_active.is_(True))
    )


def collect_conditions(
    filter_config: list[dict[str, Any]],
    query_params: dict[str, str],
    *,
    skip_key: str | None = None,
) -> list[Any]:
    """აქტიური ფილტრების პირობები.

    `skip_key` facet-ების დათვლისთვისაა: ჯგუფის საკუთარი ფილტრი გამოირიცხება,
    თორემ ბრენდის არჩევისას ბრენდების სია ერთ ჩანაწერამდე დაიშლებოდა.
    """
    conditions: list[Any] = []

    for config in filter_config:
        key = str(config["key"])
        # `category` და `price` კონფიგზე დამოუკიდებლად მუშავდება ქვემოთ —
        # კატეგორიის საკუთარ კონფიგში (brand, specs.*) `category` ჩანაწერი არ არსებობს,
        # ამიტომ ციკლში მისი დამუშავება ფილტრს ჩუმად კარგავდა
        if key in {skip_key, "category"}:
            continue
        raw = query_params.get(param_for(config))
        if not raw:
            continue
        condition = _condition(config, raw)
        if condition is not None:
            conditions.append(condition)

    if skip_key != "category" and (raw_category := query_params.get("category")):
        slugs = [s.strip() for s in raw_category.split(",") if s.strip()]
        if slugs:
            conditions.append(Category.slug.in_(slugs))

    if skip_key != "price" and (raw_price := query_params.get("price")):
        condition = _price_condition(raw_price)
        if condition is not None:
            conditions.append(condition)

    return conditions


def search_condition(term: str) -> Any:
    """დროებითი ტექსტური ძებნა — Phase 3-ში `services/search.py` ჩაანაცვლებს."""
    pattern = f"%{term.strip().lower()}%"
    return or_(
        func.lower(Product.name).like(pattern),
        func.lower(Product.short_description).like(pattern),
        func.lower(Brand.name).like(pattern),
    )


async def compute_facets(
    db: AsyncSession,
    filter_config: list[dict[str, Any]],
    query_params: dict[str, str],
    extra_conditions: list[Any],
) -> dict[str, Any]:
    """თითოეული ოფციის ხელმისაწვდომი რაოდენობა.

    სტანდარტული e-commerce ქცევა: ჯგუფის რაოდენობები ითვლება ყველა *სხვა*
    ფილტრის გათვალისწინებით. ასე ერთი ჯგუფის შიგნით ოფციები არჩევისას არ ქრება
    და მომხმარებელს ჩანს, რას მიიღებდა სხვა არჩევანით.
    """
    values: dict[str, dict[str, int]] = {}

    for config in filter_config:
        key = str(config["key"])
        column = _column_for(key)
        conditions = collect_conditions(filter_config, query_params, skip_key=key)

        stmt = (
            select(column.label("value"), func.count(Product.id).label("hits"))
            .select_from(Product)
            .join(Brand, Product.brand_id == Brand.id)
            .join(Category, Product.category_id == Category.id)
            .where(Product.is_active.is_(True), column.is_not(None))
            .group_by(column)
        )
        for condition in conditions + extra_conditions:
            stmt = stmt.where(condition)

        rows = (await db.execute(stmt)).all()
        values[key] = {str(row.value): int(row.hits) for row in rows if row.value is not None}

    # ფასის საზღვრები: min/max — მთელი (გაფილტრული) ნაკრებისა, სლაიდერის დიაპაზონისთვის;
    # current* — მიმდინარე შედეგისა
    bounds_conditions = collect_conditions(filter_config, query_params, skip_key="price")
    price_stmt = (
        select(func.min(Product.price), func.max(Product.price))
        .select_from(Product)
        .join(Brand, Product.brand_id == Brand.id)
        .join(Category, Product.category_id == Category.id)
        .where(Product.is_active.is_(True))
    )
    for condition in bounds_conditions + extra_conditions:
        price_stmt = price_stmt.where(condition)
    overall_min, overall_max = (await db.execute(price_stmt)).one()

    current_stmt = (
        select(func.min(Product.price), func.max(Product.price))
        .select_from(Product)
        .join(Brand, Product.brand_id == Brand.id)
        .join(Category, Product.category_id == Category.id)
        .where(Product.is_active.is_(True))
    )
    for condition in collect_conditions(filter_config, query_params) + extra_conditions:
        current_stmt = current_stmt.where(condition)
    current_min, current_max = (await db.execute(current_stmt)).one()

    return {
        "values": values,
        "price": {
            "min": int(overall_min or 0),
            "max": int(overall_max or 0),
            "current_min": int(current_min or 0),
            "current_max": int(current_max or 0),
        },
    }


async def list_products(
    db: AsyncSession,
    *,
    query_params: dict[str, str],
    sort: str,
    page: int,
    limit: int,
    search_term: str = "",
) -> dict[str, Any]:
    """პროდუქტების სია ფილტრებით, სორტით, პაგინაციითა და facet-ებით."""
    category_slugs = [s.strip() for s in query_params.get("category", "").split(",") if s.strip()]
    filter_config = await resolve_filter_config(db, category_slugs, bool(search_term))

    extra: list[Any] = []
    if search_term:
        extra.append(search_condition(search_term))

    conditions = collect_conditions(filter_config, query_params) + extra

    count_stmt = (
        select(func.count(Product.id))
        .select_from(Product)
        .join(Brand, Product.brand_id == Brand.id)
        .join(Category, Product.category_id == Category.id)
        .where(Product.is_active.is_(True))
    )
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
    total = int((await db.scalar(count_stmt)) or 0)

    stmt = _base_query().options(selectinload(Product.images))
    for condition in conditions:
        stmt = stmt.where(condition)

    # მარაგში არმყოფი ყოველთვის ბოლოშია, არჩეული სორტის მიუხედავად
    stmt = (
        stmt.order_by((Product.stock > 0).desc(), *SORTABLE.get(sort, SORTABLE[DEFAULT_SORT]))
        .offset((page - 1) * limit)
        .limit(limit)
    )

    items = (await db.scalars(stmt)).unique().all()
    facets = await compute_facets(db, filter_config, query_params, extra)

    return {"items": list(items), "total": total, "facets": facets}


async def get_by_slug(db: AsyncSession, slug: str) -> Product | None:
    stmt = _base_query().options(selectinload(Product.images)).where(Product.slug == slug)
    return (await db.scalars(stmt)).unique().one_or_none()


async def get_by_id(db: AsyncSession, product_id: Any) -> Product | None:
    stmt = _base_query().options(selectinload(Product.images)).where(Product.id == product_id)
    return (await db.scalars(stmt)).unique().one_or_none()


async def get_related(db: AsyncSession, product: Product, limit: int = 8) -> list[Product]:
    """მსგავსი პროდუქტები: იგივე კატეგორია, ფასის სიახლოვით.

    დავალება იმავე ბრენდს ანიჭებს უპირატესობას, frontend კი ფასის ±30% დიაპაზონს —
    ორივეს ვითვალისწინებთ სორტირებაში, ცარიელი შედეგის რისკის გარეშე.
    """
    price_distance = func.abs(Product.price - product.price)
    stmt = (
        _base_query()
        .options(selectinload(Product.images))
        .where(Product.category_id == product.category_id, Product.id != product.id)
        .order_by(
            (Product.brand_id == product.brand_id).desc(),
            price_distance.asc(),
        )
        .limit(limit)
    )
    return list((await db.scalars(stmt)).unique().all())


async def list_categories(db: AsyncSession) -> list[tuple[Category, int]]:
    stmt = (
        select(Category, func.count(Product.id))
        .outerjoin(Product, and_(Product.category_id == Category.id, Product.is_active.is_(True)))
        .group_by(Category.id)
        .order_by(Category.position, Category.name)
    )
    return [(row[0], int(row[1])) for row in (await db.execute(stmt)).all()]


async def list_brands(db: AsyncSession) -> list[tuple[Brand, int]]:
    stmt = (
        select(Brand, func.count(Product.id))
        .outerjoin(Product, and_(Product.brand_id == Brand.id, Product.is_active.is_(True)))
        .group_by(Brand.id)
        .order_by(Brand.name)
    )
    return [(row[0], int(row[1])) for row in (await db.execute(stmt)).all()]


async def home_sections(db: AsyncSession, limit: int = 8) -> dict[str, Any]:
    """მთავარი გვერდის ოთხივე სექცია ერთი გამოძახებით."""
    base = _base_query().options(selectinload(Product.images))

    new_arrivals = (
        (
            await db.scalars(
                base.where(Product.is_new.is_(True))
                .order_by(Product.created_at.desc())
                .limit(limit)
            )
        )
        .unique()
        .all()
    )

    # ფასდაკლების პროცენტით სორტი — ყველაზე მომგებიანი წინ
    discount_ratio = (Product.old_price - Product.price) / Product.old_price
    discounted = (
        (
            await db.scalars(
                base.where(Product.old_price.is_not(None))
                .order_by(discount_ratio.desc())
                .limit(limit)
            )
        )
        .unique()
        .all()
    )

    featured = (
        (await db.scalars(base.where(Product.is_featured.is_(True)).limit(limit))).unique().all()
    )

    return {
        "new_arrivals": list(new_arrivals),
        "discounted": list(discounted),
        "featured": list(featured),
        "popular_categories": await list_categories(db),
    }


def shipping_for(subtotal: Decimal) -> Decimal:
    """მიწოდების ღირებულება — ზღვარი და ტარიფი კონფიგიდან, არა კოდიდან."""
    if subtotal <= 0:
        return Decimal("0.00")
    if subtotal >= Decimal(settings.shipping_free_threshold):
        return Decimal("0.00")
    return Decimal(settings.shipping_flat_fee)
