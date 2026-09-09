"""ძებნის სერვისი.

ინდექსის სტრატეგია: `products.search_text` ინახავს წინასწარ ნორმალიზებულ
ტექსტს, რომელშიც *ერთდროულადაა*:
  · სიტყვები როგორც არის          („ყურსასმენები“)
  · მათი ფუძეები                   („ყურსასმენ“)
  · ლათინური ტრანსლიტერაცია        („qursasmenebi“, „qursasmen“)

ასე SQL-ის მხარეს რთული მორფოლოგია აღარ გვჭირდება — ტოკენის დამთხვევა ჩვეულებრივ
LIKE-ად რჩება. სვეტი მხოლოდ ჩაწერისას განახლდება (`build_search_text`), ამიტომ
ნებისმიერმა მომავალმა write-გზამ ის უნდა გამოიძახოს.

რანჟირება: სახელის ზუსტი დამთხვევა → სახელის პრეფიქსი → სახელში შემცველობა →
trigram-მსგავსება → ტეგი/specs; შემდეგ პოპულარობა.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Float, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Brand, Category, Product
from app.services.search_text import normalize, stem, tokenize
from app.services.translit import fix_layout, to_latin

# ერთ-ორსიმბოლოიანი ტოკენები („c“, „m“) ცალკე არაფერს ნიშნავს, მაგრამ
# რიცხვებთან ერთად კრიტიკულია („2 m“), ამიტომ არ ვყრით — მხოლოდ ზუსტად ვამთხვევთ
MIN_SUBSTRING_LEN = 3
# word_similarity(query, name) ეძებს *სახელის უახლოეს სიტყვას* და არა მთელ
# ტექსტთან მსგავსებას — გრძელ search_text-თან similarity() ყოველთვის დაბალია.
# გაზომვით: ბეჭდვითი შეცდომა ("samsnug") → 0.5, შემთხვევითი სიტყვა → ≤0.15
WORD_SIMILARITY_THRESHOLD = 0.4

# ხმაურის სიტყვები — მარტო მათგან შემდგარი მოთხოვნა ცარიელ შედეგს აბრუნებს
STOPWORDS = frozenset({"და", "the", "for", "with", "ის", "თუ", "ან", "or", "and"})


def _enrich(value: str) -> list[str]:
    """ერთი ნორმალიზებული სიტყვისგან — ყველა ფორმა, რომელიც ინდექსში უნდა მოხვდეს."""
    # ჯერ სტემი, მერე ტრანსლიტერაცია — შებრუნებული რიგი არ მუშაობს, რადგან
    # დაბოლოებები ქართულია და „qursasmenebi“-ს სტემერი ვერ შეამოკლებდა
    base = {value, stem(value)}
    forms = set(base)
    forms.update(to_latin(form) for form in base)
    return [form for form in forms if form]


def build_search_text(
    *,
    name: str,
    brand_name: str,
    category_name: str,
    category_slug: str,
    short_description: str,
    tags: list[str],
    specs: dict[str, Any],
) -> str:
    """პროდუქტის საძებნი ტექსტი. `products.search_text`-ში იწერება."""
    spec_values = " ".join(
        f"{key} {'დიახ' if value is True else 'არა' if value is False else value}"
        for key, value in (specs or {}).items()
    )
    sources = [
        name,
        brand_name,
        category_name,
        category_slug,
        short_description,
        " ".join(tags or []),
        spec_values,
    ]

    words: list[str] = []
    for source in sources:
        # ნორმალიზაცია ველ-ველზე — ათასეულების შერწყმა ველებს შორის არ უნდა გადავიდეს
        words.extend(normalize(source).split())

    forms: list[str] = []
    seen: set[str] = set()
    for word in words:
        for form in _enrich(word):
            if form not in seen:
                seen.add(form)
                forms.append(form)
    return " ".join(forms)


def _token_condition(token: str) -> Any:
    """ერთი ტოკენის დამთხვევა `search_text`-თან.

    ტოკენს ყველა ფორმით ვამოწმებთ (როგორც არის, ფუძე, ტრანსლიტერაცია), რადგან
    მომხმარებელი წერს „samsungi“ ან „სამსუნგი“, ინდექსში კი „samsung“ ზის.

    სამ სიმბოლოზე მოკლე ტოკენს ქვესტრიქონად ვერ ვეძებთ — „c“ ან „2“ ყველგან
    მოხვდებოდა და „USB C 2m“ კაბელების ნაცვლად ნახევარ კატალოგს დააბრუნებდა.
    ასეთებს მთელ სიტყვასთან ვამთხვევთ (სივრცეებით შემოსაზღვრული).
    """
    forms = _enrich(token)
    clauses = [
        Product.search_text.op("~")(rf"(^|\s){form}(\s|$)")
        if len(form) < MIN_SUBSTRING_LEN
        else Product.search_text.like(f"%{form}%")
        for form in forms
    ]
    return or_(*clauses) if len(clauses) > 1 else clauses[0]


def _relevance(tokens: list[str], normalized_query: str) -> Any:
    """რანჟირების ქულა.

    სახელის ზუსტი დამთხვევა უპირობოდ პირველია, შემდეგ პრეფიქსი, შემდეგ
    შემცველობა; ბოლოს trigram-მსგავსება და პოპულარობა წყვეტს ტოლ შემთხვევებს.
    """
    name_normalized = func.lower(Product.name)
    similarity = func.word_similarity(normalized_query, name_normalized)
    popularity = Product.rating * func.log(10, Product.reviews_count + 10)

    return (
        case(
            (name_normalized == normalized_query, 1000),
            (name_normalized.like(f"{normalized_query}%"), 500),
            (name_normalized.like(f"%{normalized_query}%"), 250),
            else_=0,
        )
        + cast(similarity, Float) * 100
        + cast(popularity, Float)
    )


async def search_products(
    db: AsyncSession, query: str, *, limit: int = 5, offset: int = 0
) -> list[Product]:
    """პროდუქტების ძებნა — ეტაპობრივი, სიზუსტიდან შემწყნარებლობისკენ.

    1. ზუსტი: ყველა ტოკენი უნდა მოიძებნოს (AND)
    2. იგივე, კლავიატურის განლაგების გასწორებით
    3. ბუნდოვანი: trigram-მსგავსება სახელთან — ბეჭდვითი შეცდომებისთვის
    4. ბუნდოვანი + განლაგება

    ეტაპები თანმიმდევრობითია და არა `OR`-ით შეერთებული: ბუნდოვანმა დამთხვევამ
    ზუსტი შედეგი არ უნდა გააფუჭოს. "samsung 5g" ზუსტად ერთ ტელეფონს პოულობს —
    OR-ის შემთხვევაში მასში 4G-ის მოდელიც მოხვდებოდა.
    """
    candidates = [query]
    remapped = fix_layout(query)
    if remapped != query:
        candidates.append(remapped)

    for fuzzy in (False, True):
        for candidate in candidates:
            results = await _run(db, candidate, limit=limit, offset=offset, fuzzy=fuzzy)
            if results:
                return results
    return []


async def _run(
    db: AsyncSession, query: str, *, limit: int, offset: int, fuzzy: bool
) -> list[Product]:
    tokens = [token for token in tokenize(query) if token not in STOPWORDS]
    if not tokens:
        return []

    normalized_query = normalize(query)

    if fuzzy:
        match = func.word_similarity(normalized_query, func.lower(Product.name)) > (
            WORD_SIMILARITY_THRESHOLD
        )
    else:
        match = and_(*[_token_condition(token) for token in tokens])

    stmt = (
        select(Product)
        .join(Brand, Product.brand_id == Brand.id)
        .join(Category, Product.category_id == Category.id)
        .options(selectinload(Product.images))
        .where(Product.is_active.is_(True), match)
        .order_by(
            (Product.stock > 0).desc(),
            _relevance(tokens, normalized_query).desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return list((await db.scalars(stmt)).unique().all())


def search_condition(query: str) -> Any:
    """კატალოგის სიისთვის — ფილტრებთან შესაერთებელი პირობა (`?q=`)."""
    tokens = [token for token in tokenize(query) if token not in STOPWORDS]
    if not tokens:
        return None
    return and_(*[_token_condition(token) for token in tokens])
