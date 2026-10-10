"""კალათის request/response სქემები."""

from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.limits import MAX_LINE_QUANTITY, MAX_ORDER_LINES
from app.schemas.base import ApiModel, ApiRequest


class CartLineIn(ApiRequest):
    """One line as the browser holds it.

    Only the id and the quantity are read. The browser also keeps a name, price
    and image so it can draw the cart without waiting, and those are ignored
    here on purpose - a price that arrived from a client is not one to store,
    and `services/cart.py` reads every one of them back from the catalogue.
    """

    product_id: UUID
    qty: int = Field(ge=1, le=MAX_LINE_QUANTITY)


class CartSnapshot(ApiModel):
    """What the storefront needs to draw a line, read from the catalogue now."""

    name: str
    slug: str
    image: str
    price: Decimal
    old_price: Decimal | None
    stock: int


class CartLineOut(ApiModel):
    product_id: UUID
    qty: int
    snapshot: CartSnapshot


class CartRequest(ApiRequest):
    items: list[CartLineIn] = Field(default_factory=list, max_length=MAX_ORDER_LINES)


class CartOut(ApiModel):
    items: list[CartLineOut]
