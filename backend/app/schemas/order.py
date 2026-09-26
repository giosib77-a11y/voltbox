"""შეკვეთების სქემები.

⚠️ კრიტიკული: `OrderItemRequest` მხოლოდ `productId`-სა და `qty`-ს იღებს.
ფასს ყოველთვის სერვერი განსაზღვრავს. `ApiRequest`-ს `extra="forbid"` აქვს,
ამიტომ თუ კლიენტი `price`-ს გამოგზავნის, მოთხოვნა 400-ით ჩავარდება — კონტრაქტის
რეგრესია ხმაურით უნდა გამოჩნდეს და არა ჩუმად იგნორირდეს.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.schemas.base import ApiModel, ApiRequest


class OrderItemRequest(ApiRequest):
    product_id: UUID
    # frontend-ის კალათა `qty`-ს იყენებს და არა `quantity`-ს
    qty: int = Field(ge=1, le=99)


class CustomerRequest(ApiRequest):
    """მყიდველის მონაცემები — ზუსტად ის ველები, რასაც Checkout.jsx აგზავნის."""

    first_name: str = Field(min_length=2, max_length=100)
    last_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(pattern=r"^5\d{8}$", description="Georgian mobile, digits only")
    city: str = Field(min_length=2, max_length=100)
    address: str = Field(min_length=5, max_length=500)
    comment: str = Field(default="", max_length=1000)
    # A guest's, optional: the order confirmation goes here. A signed-in
    # customer's is their account's, and the storefront does not ask for it.
    # Checked as an address because a mistyped one is a confirmation sent
    # nowhere - or to a stranger.
    email: EmailStr | None = None

    @field_validator("email", mode="before")
    @classmethod
    def blank_email_is_none(cls, value: object) -> object:
        """An emptied field is no address, not a malformed one."""
        return None if isinstance(value, str) and not value.strip() else value


#: The ways this shop can be paid. Both mean "on delivery" - there is no online
#: payment - so nothing here moves money, and a made-up value could not steal
#: anything. What it could do is arrive in the admin panel reading "already
#: paid" beside an order that is not, which is a courier handing goods over for
#: nothing. `orders.status` has had an enum from the start; this is the same
#: idea, applied to the other field an operator acts on.
PAYMENT_METHODS = ("cash", "card_on_delivery")

#: What a new order may choose - a subset of the above. Card to the courier is
#: no longer offered, but orders placed with it are still stored under that
#: value and must still load, so it stays in PAYMENT_METHODS and in the
#: column's CHECK; only POST /orders refuses it.
OFFERED_PAYMENT_METHODS = ("cash",)


class CreateOrderRequest(ApiRequest):
    items: list[OrderItemRequest] = Field(min_length=1, max_length=50)
    customer: CustomerRequest
    payment_method: Literal["cash"] = "cash"


class OrderItemSnapshot(ApiModel):
    """frontend კალათის იმავე ფორმას ელოდება: {productId, qty, snapshot}."""

    name: str
    slug: str
    image: str
    price: Decimal
    old_price: Decimal | None = None
    stock: int = 0


class OrderItemOut(ApiModel):
    product_id: UUID
    qty: int
    snapshot: OrderItemSnapshot


class OrderTotals(ApiModel):
    subtotal: Decimal
    shipping: Decimal
    total: Decimal


class OrderLookupRequest(ApiRequest):
    """A guest reading their own order.

    The contact travels in the body, never in the URL: a query string is
    written to the access log of every hop, to proxy logs and to browser
    history, and this field is a customer's phone number or email.
    """

    order_number: str = Field(min_length=3, max_length=32)
    contact: str = Field(min_length=3, max_length=255, description="Email or phone from checkout")


class CustomerOut(ApiModel):
    first_name: str
    last_name: str
    phone: str
    city: str
    address: str
    comment: str = ""


class OrderOut(ApiModel):
    order_number: str
    created_at: datetime
    status: str
    items: list[OrderItemOut]
    customer: CustomerOut
    totals: OrderTotals
    payment_method: str
    currency: str


class DeliveryCityOut(ApiModel):
    name: str
    fee: Decimal


class ShopFeaturesOut(ApiModel):
    """What this deployment can do, for the storefront to show or hide."""

    #: Whether the shop can send email at all (RESEND_API_KEY and EMAIL_FROM
    #: set). Off, a page must not promise one: the guest's confirmation field
    #: and the forgot-password link are hidden.
    email: bool


class DeliveryRulesOut(ApiModel):
    """services/delivery.py as the storefront reads it."""

    cities: list[DeliveryCityOut]
    free_from: Decimal
    currency: str
    # Here and not on an endpoint of its own: every storefront page already
    # loads this response once per session (the footer shows the free-delivery
    # threshold), so a page that needs the signal has it for no extra request.
    features: ShopFeaturesOut
