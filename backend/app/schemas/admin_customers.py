"""Admin customer schemas.

What it does: shapes the customer list and detail views.
Where it fits: app/api/v1/routes/admin/customers.py.
Notes: these models exist precisely so an ORM `User` is never returned. That is
what keeps `password_hash` out of a response, and a test asserts it.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.schemas.base import ApiModel, ApiRequest


class CustomerListItem(ApiModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    phone: str | None
    role: str
    is_active: bool
    orders_count: int
    total_spent: Decimal
    created_at: datetime


class CustomerPage(ApiModel):
    items: list[CustomerListItem]
    total: int
    page: int
    total_pages: int
    limit: int


class CustomerAddressOut(ApiModel):
    id: UUID
    label: str
    city: str
    address_line: str
    phone: str | None
    is_default: bool


class CustomerOrderOut(ApiModel):
    id: UUID
    order_number: str
    status: str
    total: Decimal
    created_at: datetime


class CustomerDetailOut(CustomerListItem):
    addresses: list[CustomerAddressOut]
    orders: list[CustomerOrderOut]


class BlockRequest(ApiRequest):
    is_active: bool
