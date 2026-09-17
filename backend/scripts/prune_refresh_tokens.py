"""Delete refresh tokens a week after they expire.

What it does: removes every refresh_tokens row whose expires_at lies more than
RETENTION in the past - spent, revoked and abandoned alike. Rotation writes a row
on every refresh and nothing else deletes one, so without this the table grows
for as long as anyone signs in.
Where it fits: run once a day by the Render cron job (docs/deployment.md §2), or
by hand from backend/ against whatever DATABASE_URL points at. `--dry-run`
counts what would go and changes nothing; run it first against any database
this has not pruned before.
Notes: why the condition is exactly what it is, and what it gives up, is written
beside RETENTION and in ASSUMPTIONS.md 8.13.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models import RefreshToken
from app.db.session import SessionLocal, engine

#: How long a row outlives its own expiry.
#:
#: Reuse detection is what needs old rows. A spent token coming back means two
#: copies of it exist, and `_handle_possible_reuse` in app/services/auth.py can
#: only end the session it belongs to while the spent row is still there to name
#: the family. The copy that matters is the owner's: when a thief rotates first,
#: the owner's browser sending the old token *is* the detection. That copy is a
#: cookie whose Max-Age is the token's own lifetime, so after expires_at the
#: browser no longer has it to send.
#:
#: Keyed on expires_at, never created_at. Each row carries its own lifetime, so
#: changing REFRESH_TOKEN_TTL_DAYS cannot make this delete a token that still
#: works, or a spent one whose owner can still present it.
#:
#: No condition on revoked_at. Most sessions end by expiring rather than by a
#: logout, so their last token is expired and unrevoked, and requiring
#: revoked_at would keep every one of those forever. Nor is a revoked row ever
#: deleted early: spent rows are the theft detector itself.
#:
#: The week covers the gap between the server's expiry and the browser's.
#: Max-Age counts from when the response arrives, the app and database clocks
#: differ by seconds, and a device whose clock ran ahead when it received the
#: cookie keeps it that much longer once the clock is corrected. A day would
#: cover the first two and a wrong timezone; a week also covers a wrong date.
#:
#: What this gives up: a spent token replayed more than a week after it expired
#: is refused as before, but no longer ends its session. What still holds: every
#: token a browser can still send is caught, and a token that old could not be
#: exchanged for a session anyway, because the refresh refuses expired tokens.
#: tests/test_prune_refresh_tokens.py pins both sides, and the cookie lifetime
#: this depends on.
RETENTION = timedelta(days=7)


def _past_retention() -> ColumnElement[bool]:
    """The one condition, so a dry run and a prune can never disagree.

    now() is the database's clock - the same one the refresh itself compares
    expires_at against.
    """
    return RefreshToken.expires_at < func.now() - RETENTION


async def count_prunable(db: AsyncSession) -> int:
    """How many rows a prune would delete right now."""
    total = await db.scalar(select(func.count()).select_from(RefreshToken).where(_past_retention()))
    return int(total or 0)


async def prune(db: AsyncSession) -> int:
    """Delete the rows past retention. Returns how many; the caller commits.

    One statement rather than batches: a daily run deletes one day's refreshes,
    the index on expires_at makes that a range scan, and a refresh never locks
    these rows - they fail its `expires_at > now()` condition before that.
    """
    result = await db.execute(
        delete(RefreshToken)
        .where(_past_retention())
        # Nothing in this session holds the rows, so there is nothing to sync.
        .execution_options(synchronize_session=False)
    )
    # AsyncSession.execute is typed as returning Result for any statement; a
    # DELETE actually returns a CursorResult, which is where rowcount lives.
    return cast("CursorResult[Any]", result).rowcount


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prune_refresh_tokens.py",
        description=f"Delete refresh tokens that expired more than {RETENTION.days} days ago",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="count what would be deleted and change nothing"
    )
    return parser


async def main() -> None:
    args = build_parser().parse_args()
    # ASCII on purpose. The line is printed after the commit, and a console or
    # pipe that cannot encode a character raises right there - Windows pipes
    # are cp1252 - which would report a prune that succeeded as a failed run.
    age = f"expired more than {RETENTION.days} days ago"
    try:
        async with SessionLocal() as db:
            if args.dry_run:
                count = await count_prunable(db)
                print(f"  dry run: {count} refresh_tokens rows {age}; nothing was deleted")
                return
            deleted = await prune(db)
            await db.commit()
        print(f"  refresh_tokens: deleted {deleted} rows {age}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
