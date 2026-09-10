"""მისამართების სქემები.

ველების ნაკრები frontend-ის ფორმას მისდევს (`../frontend/src/pages/Account/Addresses.jsx`):
label, city, address, isDefault. DB-ის დამატებითი სვეტები (fullName, phone,
apartment, postalCode) არასავალდებულოა და მომავალი გაფართოებისთვისაა.
"""

from uuid import UUID

from pydantic import Field

from app.schemas.base import ApiModel, ApiRequest


class AddressRequest(ApiRequest):
    label: str = Field(default="", max_length=100)
    city: str = Field(min_length=2, max_length=100)
    # frontend `address`-ს აგზავნის; ბაზაში სვეტს `address_line` ჰქვია, რადგან
    # `address` ცხრილის სახელს ეხლება
    address: str = Field(min_length=5, max_length=500)
    is_default: bool = False
    full_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    apartment: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)


class AddressOut(ApiModel):
    id: UUID
    label: str
    city: str
    address: str
    is_default: bool
    full_name: str | None
    phone: str | None
    apartment: str | None
    postal_code: str | None
