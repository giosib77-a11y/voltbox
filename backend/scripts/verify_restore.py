"""Did a restore actually reproduce the database?

Counting tables is not enough. A restore that quietly lost an index, a check
constraint or a column default is one that works until the day it matters - so
this compares the shape of every object and the row count of every table
between two databases.

    python scripts/verify_restore.py <restored-url> --against <source-url>

`--against` is required, and both URLs (the restored one and `--against`) must
point at localhost (localhost, 127.0.0.1 or ::1) and must not carry a `host` or
`hostaddr` query parameter: asyncpg takes those from the query and they would
override the host in the URL. The script imports nothing from `app`, so it never
loads settings or backend/.env, and it never learns the live URL; instead it
refuses every non-local database. That keeps it from ever touching the live
database. Both databases are local, so no TLS is configured. To check a restore
of a production dump, restore it locally and compare it with a local database
loaded from the same dump.

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

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import create_async_engine

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

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
    # A restore that drops ENABLE ROW LEVEL SECURITY leaves the table open to the
    # Data API's anon key and nothing else changes shape.
    "rls": """
        select c.relname||' enabled='||c.relrowsecurity||' forced='||c.relforcerowsecurity
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relkind in ('r', 'p') order by 1
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


def is_local(url: str) -> bool:
    """True only for a URL that connects to the machine running the script.

    The host must be local and the query must not name one: SQLAlchemy hands
    `url.query` to asyncpg, where `?host=` wins over the host in the URL.
    """
    try:
        parsed = make_url(url)
    except ArgumentError:
        return False
    return parsed.host in LOCAL_HOSTS and not {"host", "hostaddr"} & set(parsed.query)


async def read(url: str) -> dict[str, list[str]]:
    engine = create_async_engine(url.replace("postgresql://", "postgresql+asyncpg://"))
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
    parser.add_argument(
        "--against", required=True, help="local database to compare with (localhost only)"
    )
    args = parser.parse_args()

    for flag, url in (("restored", args.restored), ("--against", args.against)):
        if not is_local(url):
            print(
                f"refusing {flag}: the host must be localhost, 127.0.0.1 or ::1, "
                "with no host/hostaddr in the query"
            )
            return 2

    live, restored = await read(args.against), await read(args.restored)

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
