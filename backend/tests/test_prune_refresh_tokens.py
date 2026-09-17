"""scripts/prune_refresh_tokens.py, against reuse detection.

What it covers: the prune removes rows a week past their expiry and nothing that
reuse detection can still act on. A spent token coming back is how theft shows,
and `_handle_possible_reuse` can end the session only while the spent row is
there to name its family. A prune that reached too far would turn a caught theft
into an ordinary 401, with nothing failing to say so.

Both sides of the line are held here. Inside the retention a replay still ends
the session. Past it, the replay is refused and ends nothing: that is the trade
written down in ASSUMPTIONS.md 8.13, pinned so it stays a decision. The line
rests on one fact about the cookie, which is pinned as well.
"""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from app.core.config import settings
from app.core.security import hash_refresh_token
from app.db.models import RefreshToken, User
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import load_script, make_user

PRUNE = load_script("prune_refresh_tokens")

#: The httpOnly cookie the refresh token travels in.
COOKIE = settings.refresh_cookie_name

REGISTRATION = {
    "firstName": "ნინო",
    "lastName": "კაპანაძე",
    "password": "supersecret1",
}


def _days(n: float) -> datetime:
    """A moment `n` days from now; negative is in the past."""
    return datetime.now(UTC) + timedelta(days=n)


def _token(user: User, *, expires_at: datetime, revoked_at: datetime | None = None) -> RefreshToken:
    """A refresh token row built directly, in whatever state a test needs."""
    return RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(secrets.token_urlsafe(32)),
        family_id=uuid.uuid4(),
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


async def _stored(db: AsyncSession, raw_token: str) -> bool:
    """Whether the row behind this raw token is still in the table."""
    found = await db.scalar(
        select(RefreshToken.id).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    return found is not None


async def _session_with_an_expired_spent_token(
    client: httpx.AsyncClient, db: AsyncSession, *, email: str, expired_days_ago: int
) -> tuple[str, str]:
    """Sign up, rotate once, then age the spent token. → (spent, live).

    Rotated a month before it expired, as a real one would have been, so the
    replay is far outside the retry grace and reads as theft.
    """
    await client.post("/api/v1/auth/register", json={**REGISTRATION, "email": email})
    spent = client.cookies.get(COOKIE)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200
    live = client.cookies.get(COOKIE)
    assert spent and live

    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(spent))
        .values(
            revoked_at=_days(-(expired_days_ago + 29)),
            expires_at=_days(-expired_days_ago),
        )
    )
    await db.flush()
    return spent, live


async def test_rows_past_the_retention_are_deleted(db: AsyncSession) -> None:
    """Spent and abandoned alike: a week past expiry, nothing needs either.

    The abandoned one is the case that matters. Sessions usually end by expiring
    rather than by a logout, so a prune that took only revoked rows would keep
    the commonest kind of row forever.
    """
    user = await make_user(db, email="rows@example.ge")
    spent = _token(user, expires_at=_days(-8), revoked_at=_days(-37))
    abandoned = _token(user, expires_at=_days(-8))
    live = _token(user, expires_at=_days(20))
    db.add_all([spent, abandoned, live])
    await db.flush()

    assert await PRUNE.prune(db) == 2

    left = (await db.scalars(select(RefreshToken.id).where(RefreshToken.user_id == user.id))).all()
    assert left == [live.id]


async def test_a_revoked_token_that_has_not_expired_is_kept(db: AsyncSession) -> None:
    """Revoked is not the same as finished with.

    A spent token that has not expired is exactly the row a replay is checked
    against: its owner's browser can still send it. Deleting revoked rows early
    would switch theft detection off without a single auth test failing.
    """
    user = await make_user(db, email="kept@example.ge")
    spent = _token(user, expires_at=_days(20), revoked_at=_days(-1))
    db.add(spent)
    await db.flush()

    assert await PRUNE.prune(db) == 0

    stored = (
        await db.execute(
            select(RefreshToken.expires_at, RefreshToken.revoked_at).where(
                RefreshToken.id == spent.id
            )
        )
    ).one()
    assert tuple(stored) == (spent.expires_at, spent.revoked_at)


async def test_a_spent_token_inside_the_retention_still_ends_its_session(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """The row a replay needs survives the prune, and still acts.

    Expired six days ago: past its lifetime, inside the week. A browser can still
    hold it - its clock may have been ahead when the cookie arrived - and if a
    thief rotated first, that browser sending it is the moment theft shows.
    """
    spent, live = await _session_with_an_expired_spent_token(
        client, db, email="inside@example.ge", expired_days_ago=6
    )

    await PRUNE.prune(db)
    assert await _stored(db, spent)

    replay = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={spent}"})
    assert replay.status_code == 401
    # The replay ended the family, so the token it was rotated into is dead too.
    after = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={live}"})
    assert after.status_code == 401


async def test_past_the_retention_a_replay_is_refused_and_ends_nothing(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """The other side of the line, pinned so that it stays a decision.

    Eight days past expiry the spent row is gone, so the replay is an unknown
    token: refused, while the session it came from carries on. Only a copy can
    send a token this old - the owner's cookie expired with it - and the refresh
    refuses an expired token whether or not its row is still there.
    """
    spent, live = await _session_with_an_expired_spent_token(
        client, db, email="past@example.ge", expired_days_ago=8
    )

    await PRUNE.prune(db)
    assert not await _stored(db, spent)

    replay = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={spent}"})
    assert replay.status_code == 401
    after = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={live}"})
    assert after.status_code == 200


async def test_the_cookie_never_outlives_its_token_by_more_than_the_retention(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """What the retention rests on.

    A spent row may go once nobody can legitimately send its token, and the
    owner's copy lives in this cookie. Give the cookie a longer life than the
    token plus the retention, and a browser could send a token whose row the
    prune had already deleted: a caught theft would become a plain 401, and
    nothing else would fail. This does.
    """
    email = "cookie@example.ge"
    response = await client.post("/api/v1/auth/register", json={**REGISTRATION, "email": email})
    max_age = re.search(r"Max-Age=(\d+)", response.headers["set-cookie"])
    assert max_age, response.headers["set-cookie"]

    expires_at = await db.scalar(
        select(RefreshToken.expires_at)
        .join(User, User.id == RefreshToken.user_id)
        .where(User.email == email)
    )
    assert expires_at is not None

    cookie_lifetime = timedelta(seconds=int(max_age.group(1)))
    token_lifetime = expires_at - datetime.now(UTC)
    assert cookie_lifetime <= token_lifetime + PRUNE.RETENTION


async def test_a_dry_run_counts_what_a_prune_would_delete(db: AsyncSession) -> None:
    """The first run against a live database is a dry run, so it has to be right.

    Both go through one condition; this is the guard that they stay that way.
    """
    user = await make_user(db, email="dry@example.ge")
    db.add_all(
        [
            _token(user, expires_at=_days(-9), revoked_at=_days(-38)),
            _token(user, expires_at=_days(-8)),
            _token(user, expires_at=_days(-6), revoked_at=_days(-35)),
        ]
    )
    await db.flush()

    counted = await PRUNE.count_prunable(db)

    assert counted == 2
    assert await db.scalar(select(func.count()).select_from(RefreshToken)) == 3
    assert await PRUNE.prune(db) == counted
