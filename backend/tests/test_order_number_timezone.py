"""A-043 / A-077: the date in `VB-YYYYMMDD-NNNNN` is the store's day, whatever the session zone.

The store's zone is `settings.store_timezone` (default Asia/Tbilisi), the same one
the admin "today" filter uses.

`now()` cannot be faked, so the test varies the session TimeZone instead. +14 and
-12 are 26 hours apart, so a date taken from the session clock differs between
them at every wall-clock moment: the old `to_char(now(), ...)` cannot pass the
"same under both zones" check, and cannot match the store's zone in both.

Everything runs in one transaction, where `now()` is constant, so the expected
date and the order number are computed from the same instant (no midnight race).
"""

import re

import pytest
from app.core.config import Settings, settings
from app.services import order as order_service
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

NUMBER = re.compile(r"^VB-(\d{8})-\d{5}$")


async def _day_under(db: AsyncSession, zone: str) -> str:
    await db.execute(text(f"SET LOCAL TIME ZONE '{zone}'"))  # constant literal, not user input
    match = NUMBER.match(await order_service._next_order_number(db))
    assert match is not None
    return match.group(1)


async def _day_in(db: AsyncSession, zone: str) -> str:
    day = await db.scalar(
        text("SELECT to_char(now() AT TIME ZONE :zone, 'YYYYMMDD')"), {"zone": zone}
    )
    assert isinstance(day, str)
    return day


@pytest.mark.parametrize("zone", ["Pacific/Kiritimati", "Etc/GMT+12", "UTC"])
async def test_order_number_date_is_the_store_day(db: AsyncSession, zone: str) -> None:
    day = await _day_under(db, zone)

    assert day == await _day_in(db, settings.store_timezone)


async def test_order_number_date_does_not_depend_on_the_session_time_zone(
    db: AsyncSession,
) -> None:
    east = await _day_under(db, "Pacific/Kiritimati")  # UTC+14
    west = await _day_under(db, "Etc/GMT+12")  # UTC-12

    assert east == west


async def test_order_number_date_follows_settings_store_timezone(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # +14 and -12 are 26 hours apart, so their calendar days differ at every
    # moment; one fixed zone (the old Tbilisi literal) cannot match both.
    monkeypatch.setattr(settings, "store_timezone", "Pacific/Kiritimati")
    east = await _day_under(db, "UTC")
    monkeypatch.setattr(settings, "store_timezone", "Etc/GMT+12")
    west = await _day_under(db, "UTC")

    assert east == await _day_in(db, "Pacific/Kiritimati")
    assert west == await _day_in(db, "Etc/GMT+12")
    assert east != west


# -- STORE_TIMEZONE is checked when the process starts ------------------------


def _from_the_environment(monkeypatch: pytest.MonkeyPatch, zone: str | None) -> Settings:
    """Settings as the deployed process builds them: from the variable, no .env."""
    if zone is None:
        monkeypatch.delenv("STORE_TIMEZONE", raising=False)
    else:
        monkeypatch.setenv("STORE_TIMEZONE", zone)
    return Settings(
        _env_file=None,
        database_url="postgresql://voltbox:voltbox@localhost:55432/voltbox",
        jwt_secret="x" * 40,
    )


@pytest.mark.parametrize("zone", ["Not/AZone", "", "Asia/Tbilis", "America", "../etc/passwd"])
def test_an_unknown_store_timezone_stops_the_process_at_startup(
    monkeypatch: pytest.MonkeyPatch, zone: str
) -> None:
    with pytest.raises(ValidationError) as caught:
        _from_the_environment(monkeypatch, zone)

    assert "store_timezone" in str(caught.value)
    assert "STORE_TIMEZONE" in str(caught.value), "the message names the variable"


@pytest.mark.parametrize(
    ("zone", "expected"),
    [(None, "Asia/Tbilisi"), ("Asia/Tbilisi", "Asia/Tbilisi"), ("Europe/London", "Europe/London")],
)
def test_the_default_and_another_real_zone_are_accepted(
    monkeypatch: pytest.MonkeyPatch, zone: str | None, expected: str
) -> None:
    assert _from_the_environment(monkeypatch, zone).store_timezone == expected
