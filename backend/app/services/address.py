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
from app.db.models import Address


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
    )
    return list((await db.scalars(stmt)).all())


async def _get_owned(db: AsyncSession, user_id: UUID, address_id: UUID) -> Address:
    address = await db.scalar(
        select(Address).where(Address.id == address_id, Address.user_id == user_id)
    )
    if address is None:
        # სხვისი ჩანაწერიც 404-ია: 403 ამხელდა, რომ ასეთი id არსებობს
        raise NotFoundError("Address not found", code="ADDRESS_NOT_FOUND")
    return address


async def _clear_other_defaults(db: AsyncSession, user_id: UUID, keep_id: UUID | None) -> None:
    """ერთი ძირითადი მისამართი მომხმარებელზე.

    ბაზაში partial unique ინდექსია, ამიტომ ძველის გასუფთავება *იმავე*
    ტრანზაქციაში უნდა მოხდეს — თორემ ჩაწერა შეზღუდვას დაეჯახება.
    """
    stmt = update(Address).where(Address.user_id == user_id, Address.is_default.is_(True))
    if keep_id is not None:
        stmt = stmt.where(Address.id != keep_id)
    await db.execute(stmt.values(is_default=False))


async def create(db: AsyncSession, user_id: UUID, payload: AddressData) -> list[Address]:
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
