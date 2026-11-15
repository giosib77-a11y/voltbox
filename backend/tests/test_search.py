"""Phase 3 — ქართული ძებნის ტესტები.

დაფარულია §9-ის სავალდებულო სცენარები (ქართული, ტრანსლიტერაცია, არასწორი
განლაგება, შეცდომა, ცარიელი, მხოლოდ სტოპ-სიტყვები) და frontend-ის ოთხივე
acceptance-ქეისი, რომელიც README-შია დაფიქსირებული.
"""

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from app.db.session import engine
from app.services.search import MAX_QUERY_TOKENS, _parse_query
from app.services.search_text import normalize, stem, tokenize
from app.services.translit import fix_layout, to_latin
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_brand, make_category, make_product

# --------------------------------------------------------------------------- #
#  ნორმალიზაცია — სუფთა ფუნქციები, ბაზის გარეშე                                #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("20 000", "20000"),
        ("20,000 mAh", "20000 mah"),
        ("USB-C 2m", "usb c 2 m"),
        ("USB-C კაბელი 2 მ", "usb c კაბელი 2 m"),
        ('6.2" AMOLED', "6.2 in amoled"),
        ("Anker PowerCore 20000mAh", "anker powercore 20000 mah"),
        ("40 სთ", "40 h"),
    ],
)
def test_normalize_unifies_separators_and_units(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_normalize_does_not_merge_unrelated_numbers() -> None:
    # "iPhone 15" + "128GB" არ უნდა გახდეს "15128"
    assert normalize("iPhone 15 128GB") == "iphone 15 128 gb"


def test_stem_reduces_georgian_inflections() -> None:
    assert stem("ყურსასმენები") == stem("ყურსასმენი") == "ყურსასმენ"


def test_stem_handles_transliterated_suffixes() -> None:
    # მომხმარებელი წერს "samsungi", ინდექსში "samsung" ზის
    assert stem("samsungi") == "samsung"


def test_transliteration_is_stable() -> None:
    assert to_latin("კაბელი") == "kabeli"
    assert to_latin("ყურსასმენები") == "qursasmenebi"


def test_keyboard_layout_maps_both_directions() -> None:
    assert fix_layout("samsungi") == "სამსუნგი"
    assert fix_layout("სამსუნგი") == "samsungi"


def test_empty_query_produces_no_tokens() -> None:
    assert tokenize("") == []
    assert tokenize("   ") == []


# --------------------------------------------------------------------------- #
#  ბაზაზე დაფუძნებული ძებნა                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
async def searchable(db: AsyncSession) -> None:
    """მინი-კატალოგი, რომელიც ოთხივე acceptance-ქეისს ფარავს."""
    phones = await make_category(db, "phones")
    cables = await make_category(db, "cables", filters=[])
    powerbanks = await make_category(db, "powerbanks", filters=[])
    headphones = await make_category(db, "headphones", filters=[])

    samsung = await make_brand(db, "Samsung", "სამხრეთ კორეა")
    anker = await make_brand(db, "Anker", "ჩინეთი")
    jbl = await make_brand(db, "JBL", "აშშ")
    baseus = await make_brand(db, "Baseus", "ჩინეთი")

    await make_product(
        db,
        phones,
        samsung,
        slug="galaxy-s24",
        name="Samsung Galaxy S24 256GB",
        specs={"network": "5G", "ram": "8 GB"},
    )
    await make_product(
        db,
        phones,
        samsung,
        slug="galaxy-a15",
        name="Samsung Galaxy A15 128GB",
        specs={"network": "4G", "ram": "6 GB"},
    )
    await make_product(
        db,
        powerbanks,
        anker,
        slug="powercore-20000",
        name="Anker PowerCore 20000mAh",
        specs={"capacity": "20 000 mAh"},
    )
    await make_product(
        db,
        powerbanks,
        anker,
        slug="powercore-10000",
        name="Anker PowerCore 10000mAh",
        specs={"capacity": "10 000 mAh"},
    )
    await make_product(
        db,
        cables,
        baseus,
        slug="usb-c-2m",
        name="Baseus USB-C — USB-C კაბელი 2მ",
        specs={"connector": "USB-C — USB-C", "length": "2 მ"},
    )
    await make_product(
        db,
        cables,
        baseus,
        slug="usb-c-1m",
        name="Baseus USB-C — Lightning კაბელი 1მ",
        specs={"connector": "USB-C — Lightning", "length": "1 მ"},
    )
    await make_product(
        db,
        headphones,
        jbl,
        slug="tune-520bt",
        name="JBL Tune 520BT",
        specs={"type": "On-ear", "wireless": True},
        short_description="უსადენო ყურსასმენი",
    )


async def _names(client: httpx.AsyncClient, query: str, limit: int = 10) -> list[str]:
    response = await client.get("/api/v1/search", params={"q": query, "limit": limit})
    assert response.status_code == 200
    return [item["name"] for item in response.json()]


async def test_acceptance_case_thousand_separator(
    client: httpx.AsyncClient, searchable: None
) -> None:
    names = await _names(client, "20 000")

    assert names == ["Anker PowerCore 20000mAh"]


async def test_acceptance_case_usb_c_two_meters(
    client: httpx.AsyncClient, searchable: None
) -> None:
    names = await _names(client, "USB C 2m")

    assert "Baseus USB-C — USB-C კაბელი 2მ" in names
    assert "Baseus USB-C — Lightning კაბელი 1მ" not in names


async def test_acceptance_case_samsung_5g(client: httpx.AsyncClient, searchable: None) -> None:
    names = await _names(client, "samsung 5g")

    assert names == ["Samsung Galaxy S24 256GB"]


async def test_acceptance_case_georgian_wireless_headphones(
    client: httpx.AsyncClient, searchable: None
) -> None:
    names = await _names(client, "უსადენო ყურსასმენი")

    assert names == ["JBL Tune 520BT"]


async def test_latin_transliteration_of_a_georgian_word(
    client: httpx.AsyncClient, searchable: None
) -> None:
    # "kabeli" → "კაბელი"
    names = await _names(client, "kabeli")

    assert len(names) == 2
    assert all("კაბელი" in name for name in names)


async def test_georgian_spelling_of_a_latin_brand(
    client: httpx.AsyncClient, searchable: None
) -> None:
    names = await _names(client, "სამსუნგი")

    assert len(names) == 2
    assert all(name.startswith("Samsung") for name in names)


async def test_wrong_keyboard_layout_is_recovered(
    client: httpx.AsyncClient, searchable: None
) -> None:
    """განლაგება არ გადაურთავს.

    "ყურსასმენი"-ს აკრეფა ქართულ განლაგებაზე იძლევა "yursasmeni"-ს. ეს ფორმა
    ინდექსში არ არის — ტრანსლიტერაცია "qursasmeni"-ს ინახავს (ყ→q, არა y) —
    ამიტომ მხოლოდ განლაგების გასწორება შველის.
    """
    names = await _names(client, "yursasmeni")

    assert names == ["JBL Tune 520BT"]


async def test_typo_is_tolerated_by_trigram_similarity(
    client: httpx.AsyncClient, searchable: None
) -> None:
    # ერთი გადასმული სიმბოლო: "samsnug"
    names = await _names(client, "samsnug")

    assert any(name.startswith("Samsung") for name in names)


async def test_empty_query_returns_nothing(client: httpx.AsyncClient, searchable: None) -> None:
    assert await _names(client, "") == []
    assert await _names(client, "   ") == []


async def test_stopwords_only_query_returns_nothing(
    client: httpx.AsyncClient, searchable: None
) -> None:
    assert await _names(client, "და the") == []


# --------------------------------------------------------------------------- #
#  A query is read up to MAX_QUERY_TOKENS words                                #
# --------------------------------------------------------------------------- #

# Eight real words, all found in "Samsung Galaxy S24 256GB" (name, spec values).
EIGHT_WORDS = "samsung galaxy s24 5g 8 gb 256 gb"


async def _found(client: httpx.AsyncClient, route: str, query: str) -> list[str]:
    """Names found for `query` by `/search` or by `/products?q=`."""
    response = await client.get(f"/api/v1/{route}", params={"q": query, "limit": 20})
    assert response.status_code == 200
    body = response.json()
    items = body["items"] if route == "products" else body
    return [item["name"] for item in items]


@pytest.fixture
def statements() -> Iterator[list[tuple[str, str]]]:
    """Every SQL statement sent while the test runs, with its parameters as text."""
    seen: list[tuple[str, str]] = []

    def record(conn: Any, cursor: Any, statement: str, parameters: Any, *args: Any) -> None:
        seen.append((statement, str(parameters)))

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)


def test_a_query_within_the_cap_is_read_whole() -> None:
    assert len(EIGHT_WORDS.split()) == MAX_QUERY_TOKENS
    tokens, normalized = _parse_query(EIGHT_WORDS)

    assert tokens == EIGHT_WORDS.split()
    assert normalized == normalize(EIGHT_WORDS)


def test_a_longer_query_is_cut_after_its_eighth_word() -> None:
    tokens, normalized = _parse_query(f"{EIGHT_WORDS} zzzz yyyy")

    assert tokens == EIGHT_WORDS.split()
    assert normalized == EIGHT_WORDS


def test_stopwords_do_not_count_toward_the_cap() -> None:
    query = "samsung and galaxy the s24 for 5g with 8 or gb 256 and gb zzzz"
    tokens, normalized = _parse_query(query)

    assert tokens == EIGHT_WORDS.split()
    assert "zzzz" not in normalized
    assert "and" in normalized  # kept: the query is cut at the ninth real word, not earlier


@pytest.mark.parametrize("route", ["search", "products"])
async def test_a_query_of_eight_words_still_finds_the_product(
    client: httpx.AsyncClient, searchable: None, route: str
) -> None:
    assert await _found(client, route, EIGHT_WORDS) == ["Samsung Galaxy S24 256GB"]


@pytest.mark.parametrize("route", ["search", "products"])
async def test_words_past_the_eighth_are_ignored(
    client: httpx.AsyncClient, searchable: None, route: str
) -> None:
    junk = " ".join(f"junk{n}" for n in range(20))

    assert await _found(client, route, f"{EIGHT_WORDS} {junk}") == await _found(
        client, route, EIGHT_WORDS
    )
    assert await _found(client, route, f"{EIGHT_WORDS} {junk}") == ["Samsung Galaxy S24 256GB"]


@pytest.mark.parametrize("route", ["search", "products"])
async def test_stopwords_between_the_words_do_not_use_up_the_cap(
    client: httpx.AsyncClient, searchable: None, route: str
) -> None:
    query = "samsung and galaxy the s24 for 5g with 8 or gb 256 and gb zzzz"

    assert await _found(client, route, query) == ["Samsung Galaxy S24 256GB"]


@pytest.mark.parametrize("route", ["search", "products"])
async def test_a_hundred_one_letter_words_is_a_normal_request(
    client: httpx.AsyncClient, searchable: None, route: str
) -> None:
    # The scenario of A-045: 100 one-letter words (199 characters, inside max_length).
    response = await client.get(f"/api/v1/{route}", params={"q": " ".join("a" * 100)})

    assert response.status_code == 200


@pytest.mark.parametrize("route", ["search", "products"])
async def test_the_sql_of_a_long_query_has_at_most_eight_word_conditions(
    client: httpx.AsyncClient, searchable: None, statements: list[tuple[str, str]], route: str
) -> None:
    words = [f"zq{chr(97 + n)}x" for n in range(30)]  # 30 distinct words nothing matches
    statements.clear()

    await _found(client, route, " ".join(words))

    # Words that reach the database in each statement: the products query, its count
    # and the facets (which repeat the condition) all carry the same eight at most.
    sent = [{word for word in words if word in params} for _, params in statements]
    assert max(len(found) for found in sent) == MAX_QUERY_TOKENS
    assert not any(word in params for _, params in statements for word in words[MAX_QUERY_TOKENS:])


async def test_the_typo_stage_does_not_receive_the_whole_query(
    client: httpx.AsyncClient, searchable: None, statements: list[tuple[str, str]]
) -> None:
    junk = [f"junk{n}" for n in range(20)]
    statements.clear()

    await _found(client, "search", " ".join(["samsnug", *junk]))

    assert any("word_similarity" in sql for sql, _ in statements)
    assert not any(junk[MAX_QUERY_TOKENS] in params for _, params in statements)


async def test_suggestion_payload_is_lightweight(
    client: httpx.AsyncClient, searchable: None
) -> None:
    response = await client.get("/api/v1/search", params={"q": "anker"})

    assert set(response.json()[0]) == {"id", "slug", "name", "brand", "price", "images"}
