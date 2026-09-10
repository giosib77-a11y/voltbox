"""Slug generation.

What it does: turns a Georgian or Latin name into a URL-safe slug and makes it
unique within a table.
Where it fits: used by the admin category, brand and product endpoints when the
author leaves the slug empty.
Notes: the transliteration table is the national romanization without
apostrophes. Apostrophes distinguish aspirated pairs (ტ/თ, კ/ქ, პ/ფ, ჭ/ჩ, წ/ც)
but they cannot appear in a URL, so those pairs collapse - `თ` and `ტ` both
become `t`. That is a deliberate trade: a readable, stable URL beats a
reversible one, and uniqueness is enforced separately anyway.
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

KA_TO_LATIN = {
    "ა": "a",
    "ბ": "b",
    "გ": "g",
    "დ": "d",
    "ე": "e",
    "ვ": "v",
    "ზ": "z",
    "თ": "t",
    "ი": "i",
    "კ": "k",
    "ლ": "l",
    "მ": "m",
    "ნ": "n",
    "ო": "o",
    "პ": "p",
    "ჟ": "zh",
    "რ": "r",
    "ს": "s",
    "ტ": "t",
    "უ": "u",
    "ფ": "p",
    "ქ": "k",
    "ღ": "gh",
    "ყ": "q",
    "შ": "sh",
    "ჩ": "ch",
    "ც": "ts",
    "ძ": "dz",
    "წ": "ts",
    "ჭ": "ch",
    "ხ": "kh",
    "ჯ": "j",
    "ჰ": "h",
}

MAX_SLUG_LENGTH = 200


def transliterate(text: str) -> str:
    """Georgian letters to Latin; everything else is left alone."""
    return "".join(KA_TO_LATIN.get(char, char) for char in text)


def slugify(value: str, *, max_length: int = MAX_SLUG_LENGTH) -> str:
    """A lowercase `[a-z0-9-]` slug.

    Accented Latin is decomposed and stripped (é -> e) so a name copied from a
    supplier's catalogue does not produce an unreachable URL.
    """
    text = transliterate(value.strip().lower())
    # NFKD splits "é" into "e" + combining accent; the accent is then dropped.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return text[:max_length].rstrip("-")


async def unique_slug(
    db: AsyncSession,
    column: InstrumentedAttribute[str],
    desired: str,
    *,
    exclude_id: object | None = None,
    id_column: InstrumentedAttribute[object] | None = None,
) -> str:
    """`desired`, or `desired-2`, `desired-3`... until it is free.

    Used when generating a slug from a name. An explicitly supplied slug is not
    silently renamed - a duplicate there is a 409, because quietly changing what
    the author typed produces a URL they did not expect.
    """
    base = desired or "item"
    candidate = base
    suffix = 1

    while True:
        stmt = select(func.count()).select_from(column.parent).where(column == candidate)
        if exclude_id is not None and id_column is not None:
            stmt = stmt.where(id_column != exclude_id)
        taken = await db.scalar(stmt)
        if not taken:
            return candidate
        suffix += 1
        tail = f"-{suffix}"
        candidate = f"{base[: MAX_SLUG_LENGTH - len(tail)].rstrip('-')}{tail}"
