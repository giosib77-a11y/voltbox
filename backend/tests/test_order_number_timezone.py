"""A-043: the date in `VB-YYYYMMDD-NNNNN` is the Tbilisi day, whatever the session zone.

`now()` cannot be faked, so the test varies the session TimeZone instead. +14 and
-12 are 26 hours apart, so a date taken from the session clock differs between
them at every wall-clock moment: the old `to_char(now(), ...)` cannot pass the
"same under both zones" check, and cannot match Tbilisi in both.

Everything runs in one transaction, where `now()` is constant, so the expected
date and the order number are computed from the same instant (no midnight race).
"""

import re

import pytest
from app.services import order as order_service
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

NUMBER = re.compile(r"^VB-(\d{8})-\d{5}$")


async def _day_under(db: AsyncSession, zone: str) -> str:
    await db.execute(text(f"SET LOCAL TIME ZONE '{zone}'"))  # constant literal, not user input
    match = NUMBER.match(await order_service._next_order_number(db))
    assert match is not None
    return match.group(1)


@pytest.mark.parametrize("zone", ["Pacific/Kiritimati", "Etc/GMT+12", "UTC"])
async def test_order_number_date_is_the_tbilisi_day(db: AsyncSession, zone: str) -> None:
    day = await _day_under(db, zone)
    tbilisi = await db.scalar(text("SELECT to_char(now() AT TIME ZONE 'Asia/Tbilisi', 'YYYYMMDD')"))

    assert day == tbilisi


async def test_order_number_date_does_not_depend_on_the_session_time_zone(
    db: AsyncSession,
) -> None:
    east = await _day_under(db, "Pacific/Kiritimati")  # UTC+14
    west = await _day_under(db, "Etc/GMT+12")  # UTC-12

    assert east == west
