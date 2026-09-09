"""მისამართების მარშრუტები — ყველა ავტორიზაციას ითხოვს."""

from uuid import UUID

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, Db
from app.db.models import Address
from app.schemas.address import AddressOut, AddressRequest
from app.services import address as address_service

router = APIRouter(prefix="/addresses", tags=["addresses"])


def _to_out(address: Address) -> AddressOut:
    # `address_line` → `address`: ბაზაში სვეტი ცხრილის სახელს ეხლებოდა,
    # API-ში კი frontend `address`-ს ელოდება
    return AddressOut(
        id=address.id,
        label=address.label,
        city=address.city,
        address=address.address_line,
        is_default=address.is_default,
        full_name=address.full_name,
        phone=address.phone,
        apartment=address.apartment,
        postal_code=address.postal_code,
    )


@router.get(
    "",
    summary="List the current user's addresses",
    response_model=list[AddressOut],
)
async def list_addresses(db: Db, user: CurrentUser) -> list[AddressOut]:
    return [_to_out(a) for a in await address_service.list_for_user(db, user.id)]


@router.post(
    "",
    summary="Create an address",
    status_code=status.HTTP_201_CREATED,
    description="Returns the full list so the client can replace its state in one step.",
    response_model=list[AddressOut],
)
async def create_address(db: Db, user: CurrentUser, payload: AddressRequest) -> list[AddressOut]:
    # ქართული ახსნა: სრულ სიას ვაბრუნებთ და არა ერთ ჩანაწერს, რადგან
    # `isDefault`-ის დაყენება *სხვა* მისამართებსაც ცვლის — ერთი ობიექტის
    # დაბრუნება კლიენტს მოძველებულ მდგომარეობას დაუტოვებდა
    addresses = await address_service.create(db, user.id, payload)
    await db.commit()
    return [_to_out(a) for a in addresses]


@router.put("/{address_id}", summary="Replace an address", response_model=list[AddressOut])
async def update_address(
    db: Db, user: CurrentUser, address_id: UUID, payload: AddressRequest
) -> list[AddressOut]:
    addresses = await address_service.update_one(db, user.id, address_id, payload)
    await db.commit()
    return [_to_out(a) for a in addresses]


@router.delete("/{address_id}", summary="Delete an address", response_model=list[AddressOut])
async def delete_address(db: Db, user: CurrentUser, address_id: UUID) -> list[AddressOut]:
    addresses = await address_service.remove(db, user.id, address_id)
    await db.commit()
    return [_to_out(a) for a in addresses]
