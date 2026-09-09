"""შეკვეთების სქემები.

⚠️ კრიტიკული: `OrderItemRequest` მხოლოდ `productId`-სა და `qty`-ს იღებს.
ფასს ყოველთვის სერვერი განსაზღვრავს. `ApiRequest`-ს `extra="forbid"` აქვს,
ამიტომ თუ კლიენტი `price`-ს გამოგზავნის, მოთხოვნა 400-ით ჩავარდება — კონტრაქტის
რეგრესია ხმაურით უნდა გამოჩნდეს და არა ჩუმად იგნორირდეს.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

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
    email: str | None = Field(default=None, max_length=255)


class CreateOrderRequest(ApiRequest):
    items: list[OrderItemRequest] = Field(min_length=1, max_length=50)
    customer: CustomerRequest
    payment_method: str = Field(default="cash", max_length=32)


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
