"""Did a restore actually reproduce the database?

Counting tables is not enough. A restore that quietly lost an index, a check
constraint or a column default is one that works until the day it matters - so
this compares the shape of every object and the row count of every table
between two databases.

    python scripts/verify_restore.py <restored-url>

The live database is read from DATABASE_URL in backend/.env, read-only. Pass
`--against <url>` to compare two databases neither of which is the live one.

Written after a drill on 2026-09-13 where everything matched except three
CHECK constraints, which turned out to be the same constraints printed
differently: pg_dump distributes the cast in `ANY (ARRAY[...])` one way and the
server another. That is worth knowing before somebody spends an evening on it,
so the difference is reported as EXPECTED rather than hidden.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.ssl import build_connect_args

#: Read at import time: dotenv touches the filesystem, and doing that inside an
#: async function is a blocking call in the middle of an event loop.
LIVE_URL = dotenv_values(Path(__file__).resolve().parents[1] / ".env").get("DATABASE_URL")

QUERIES = {
    "tables": """
        select table_name from information_schema.tables
        where table_schema='public' and table_type='BASE TABLE' order by 1
    """,
    "columns": """
        select table_name||'.'||column_name||' '||data_type||' '||is_nullable||
               ' '||coalesce(column_default,'-')
        from information_schema.columns where table_schema='public' order by 1
    """,
    "indexes": """
        select indexname||' :: '||indexdef from pg_indexes
        where schemaname='public' order by 1
    """,
    "constraints": """
        select conrelid::regclass||' '||conname||' '||pg_get_constraintdef(oid)
        from pg_constraint where connamespace='public'::regnamespace order by 1
    """,
    "sequences": """
        select sequence_name from information_schema.sequences
        where sequence_schema='public' order by 1
    """,
}


def normalise(value: str) -> str:
    """Flatten the one difference a dump/restore round trip really makes.

    These two are the same constraint:

        ANY ((ARRAY['a'::character varying, ...])::text[])      -- the server
        ANY (ARRAY[('a'::character varying)::text, ...])        -- after a dump

    Only the placement of the cast and its brackets differ. Rather than try to
    parse that, the comparison drops casts, brackets and whitespace entirely -
    so what is compared is which columns and which literals a constraint names.
    That is exactly the question being asked: did the restore lose a rule, or
    change which values it allows?
    """
    without_casts = re.sub(r"::[a-z ]+(\[\])?", "", value)
    return re.sub(r"[\s()\[\]]+", "", without_casts)


async def read(url: str) -> dict[str, list[str]]:
    engine = create_async_engine(
        url.replace("postgresql://", "postgresql+asyncpg://"),
        connect_args=build_connect_args() if "supabase" in url else {},
    )
    out: dict[str, list[str]] = {}
    async with engine.connect() as conn:
        for name, sql in QUERIES.items():
            out[name] = [row[0] for row in await conn.execute(text(sql))]
        rows = []
        for table in out["tables"]:
            # The name comes from information_schema and is quoted; there is no
            # caller-supplied input anywhere in this script.
            counted = await conn.execute(
                text(f'select count(*) from public."{table}"')  # noqa: S608
            )
            rows.append(f"{table}={counted.scalar()}")
        out["rows"] = rows
    await engine.dispose()
    return out


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("restored", help="URL of the database restored from the dump")
    parser.add_argument("--against", help="compare against this instead of the live database")
    args = parser.parse_args()

    source = args.against or LIVE_URL
    if not source:
        print("no source database: pass --against or set DATABASE_URL in .env")
        return 2

    live, restored = await read(source), await read(args.restored)

    real, expected = 0, 0
    for name in [*QUERIES, "rows"]:
        a = {normalise(v) for v in live[name]}
        b = {normalise(v) for v in restored[name]}
        raw_a, raw_b = set(live[name]), set(restored[name])
        differs = sorted(a ^ b)
        cosmetic = len(raw_a ^ raw_b) - len(differs)

        status = "OK" if not differs else "DIFFERS"
        note = f"  ({cosmetic} cosmetic)" if cosmetic else ""
        print(f"  [{status:7}] {name:12} source {len(a):4}   restored {len(b):4}{note}")
        for item in differs[:5]:
            print(f"              {item[:110]}")
        real += len(differs)
        expected += cosmetic

    print()
    print(f"  real mismatches     : {real}")
    print(f"  cosmetic (expected) : {expected}")
    return 1 if real else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
