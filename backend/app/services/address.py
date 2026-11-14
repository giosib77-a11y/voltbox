"""მისამართების ბიზნეს-ლოგიკა.

ორი წესი, რომელიც სერვისში ცხოვრობს და არა router-ში:
  1. ყველა ოპერაცია `current_user.id`-ით არის შემოსაზღვრული
  2. სხვისი მისამართი 404-ია და არა 403 — არსებობის გაჟონვას ვერიდებით
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import Address, User


class AddressData(Protocol):
    """სერვისს API-ის სქემაზე დამოკიდებულება არ სჭირდება — მხოლოდ ეს ველები.

    `AddressRequest` ამ პროტოკოლს ავტომატურად აკმაყოფილებს (structural typing).
    """

    label: str
    city: str
    address: str
    is_default: bool
    full_name: str | None
    phone: str | None
    apartment: str | None
    postal_code: str | None


async def list_for_user(db: AsyncSession, user_id: UUID) -> list[Address]:
    stmt = (
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(Address.is_default.desc(), Address.created_at)
        # The answer reflects the database after the write, not whatever copies
        # this session loaded earlier (see `_get_owned`).
        .execution_options(populate_existing=True)
    )
    return list((await db.scalars(stmt)).all())


async def _get_owned(db: AsyncSession, user_id: UUID, address_id: UUID) -> Address:
    # populate_existing: on the real route `get_current_user` has already loaded
    # the user on this session, and `User.addresses` is lazy="selectin", so every
    # address is in the identity map from before the lock was taken. A plain
    # SELECT returns those objects with their old attributes, and the ORM writes
    # only what differs from them: an address that looked like the default would
    # never be written back as one. Re-reading it after the lock makes the row
    # the authority.
    address = await db.scalar(
        select(Address)
        .where(Address.id == address_id, Address.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    if address is None:
        # სხვისი ჩანაწერიც 404-ია: 403 ამხელდა, რომ ასეთი id არსებობს
        raise NotFoundError("Address not found", code="ADDRESS_NOT_FOUND")
    return address


async def _lock_default_writes(db: AsyncSession, user_id: UUID) -> None:
    """Serialize the transactions that may move one user's default address.

    "Clear the old default, then write the new one" is two statements, and under
    READ COMMITTED a second transaction's clear cannot see the first one's
    uncommitted default: both clear nothing, both write a default, and the later
    one dies on `uq_addresses_one_default_per_user` (a 500 for the shopper).
    Queueing on the owner's row makes the second transaction's clear run after
    the first has committed, so it finds and clears that default.

    FOR NO KEY UPDATE, the level `auth.py` takes on the same row: it conflicts
    with itself (that is the queue) but not with the FOR KEY SHARE that any
    insert referencing the user takes (orders, tokens, addresses), so nothing
    else waits on this. No deadlock: a transaction that holds this lock goes on
    to touch only `addresses` rows, and nothing that locks an address row first
    ever asks for the user's row afterwards.
    """
    await db.execute(select(User.id).where(User.id == user_id).with_for_update(key_share=True))


async def _clear_other_defaults(db: AsyncSession, user_id: UUID, keep_id: UUID | None) -> None:
    """ერთი ძირითადი მისამართი მომხმარებელზე.

    ბაზაში partial unique ინდექსია, ამიტომ ძველის გასუფთავება *იმავე*
    ტრანზაქციაში უნდა მოხდეს — თორემ ჩაწერა შეზღუდვას დაეჯახება.
    Callers hold `_lock_default_writes` first.
    """
    stmt = update(Address).where(Address.user_id == user_id, Address.is_default.is_(True))
    if keep_id is not None:
        stmt = stmt.where(Address.id != keep_id)
    await db.execute(stmt.values(is_default=False))


async def create(db: AsyncSession, user_id: UUID, payload: AddressData) -> list[Address]:
    if payload.is_default:
        # Only a new default can clash on the index; a plain address never waits.
        await _lock_default_writes(db, user_id)
        await _clear_other_defaults(db, user_id, keep_id=None)

    address = Address(
        user_id=user_id,
        label=payload.label,
        city=payload.city,
        address_line=payload.address,
        is_default=payload.is_default,
        full_name=payload.full_name,
        phone=payload.phone,
        apartment=payload.apartment,
        postal_code=payload.postal_code,
    )
    db.add(address)
    await db.flush()
    return await list_for_user(db, user_id)


async def update_one(
    db: AsyncSession, user_id: UUID, address_id: UUID, payload: AddressData
) -> list[Address]:
    # Always, and before the read: the ORM writes only the columns that differ
    # from what it loaded, so an address read before waiting could be written
    # against a default another transaction has since moved.
    await _lock_default_writes(db, user_id)
    address = await _get_owned(db, user_id, address_id)

    if payload.is_default:
        await _clear_other_defaults(db, user_id, keep_id=address_id)

    address.label = payload.label
    address.city = payload.city
    address.address_line = payload.address
    address.is_default = payload.is_default
    address.full_name = payload.full_name
    address.phone = payload.phone
    address.apartment = payload.apartment
    address.postal_code = payload.postal_code

    await db.flush()
    return await list_for_user(db, user_id)


async def remove(db: AsyncSession, user_id: UUID, address_id: UUID) -> list[Address]:
    await _get_owned(db, user_id, address_id)
    await db.execute(delete(Address).where(Address.id == address_id))
    return await list_for_user(db, user_id)
