"""მისამართების ბიზნეს-ლოგიკა.

ორი წესი, რომელიც სერვისში ცხოვრობს და არა router-ში:
  1. ყველა ოპერაცია `current_user.id`-ით არის შემოსაზღვრული
  2. სხვისი მისამართი 404-ია და არა 403 — არსებობის გაჟონვას ვერიდებით
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.db.models import Address, User

#: The owner's cap on saved addresses per account (A-041). Without one a single
#: account could hold thousands of 500-character rows, and the list endpoint
#: returns all of them in one response. Twenty is far more than a household
#: needs; past it the shopper deletes one, and the 409 says so.
MAX_ADDRESSES_PER_USER = 20


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
    # populate_existing: this runs after the lock, and anything this session
    # loaded before it is a copy from before another transaction committed. A
    # plain SELECT returns such an object with its old attributes, and the ORM
    # writes only what differs from them: an address that looked like the default
    # would never be written back as one. Re-reading it after the lock makes the
    # row the authority. `get_current_user` no longer loads the addresses (A-041),
    # so on the route nothing is stale today; the option keeps it that way if
    # an address is ever loaded earlier on the session.
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
    """Serialize one user's address writes that could break an invariant.

    Two invariants hang on this: one default per user, and at most
    `MAX_ADDRESSES_PER_USER` addresses (`create` counts, then inserts). Both are
    "read, then write", which two concurrent transactions would each pass.

    The default: "clear the old default, then write the new one" is two
    statements, and under READ COMMITTED a second transaction's clear cannot see
    the first one's uncommitted default: both clear nothing, both write a
    default, and the later one dies on `uq_addresses_one_default_per_user` (a
    500 for the shopper). Queueing on the owner's row makes the second
    transaction's clear run after the first has committed, so it finds and
    clears that default.

    The limit: two creates at 19 would both count 19 and leave 21. Queued, the
    second counts after the first has committed.

    A plain create (no default) queues here too, but only behind the same
    user's other address writes - one account's creates never wait on another's.

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
    # Always, not only for a new default: the limit below is "count, then insert",
    # and two creates at 19 that both counted 19 would leave the account with 21.
    # Queueing on the owner's row makes the second count run after the first has
    # committed. The cost: a plain create now waits for this user's own other
    # address writes - nobody else's.
    await _lock_default_writes(db, user_id)
    held = await db.scalar(
        select(func.count()).select_from(Address).where(Address.user_id == user_id)
    )
    if (held or 0) >= MAX_ADDRESSES_PER_USER:
        raise ConflictError(
            f"An account can hold at most {MAX_ADDRESSES_PER_USER} addresses",
            code="ADDRESS_LIMIT_REACHED",
            details={"limit": MAX_ADDRESSES_PER_USER},
        )

    if payload.is_default:
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
