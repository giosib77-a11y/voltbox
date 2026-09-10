"""Admin order, inventory and dashboard schemas.

What it does: shapes the admin's order list and detail, the inventory views and
the dashboard payload.
Where it fits: the routes under app/api/v1/routes/admin/.
Notes: the order detail carries `allowedTransitions` so the UI renders only the
moves the server would accept, instead of re-implementing the state machine.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.base import ApiModel, ApiRequest


class OrderListItem(ApiModel):
    id: UUID
    order_number: str
    status: str
    customer_name: str
    phone: str | None
    email: str | None
    city: str | None
    total: Decimal
    item_count: int
    payment_method: str
    created_at: datetime


class OrderPage(ApiModel):
    items: list[OrderListItem]
    total: int
    page: int
    total_pages: int
    limit: int


class OrderItemOut(ApiModel):
    id: UUID
    product_id: UUID
    product_name: str
    product_slug: str
    image_url: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class StatusHistoryOut(ApiModel):
    from_status: str
    to_status: str
    changed_by: UUID | None
    note: str | None
    created_at: datetime


class OrderDetailOut(OrderListItem):
    customer: dict[str, Any]
    shipping_address: dict[str, Any]
    subtotal: Decimal
    shipping: Decimal
    currency: str
    notes: str | None
    items: list[OrderItemOut]
    allowed_transitions: list[str]
    history: list[StatusHistoryOut]


class StatusChangeRequest(ApiRequest):
    to: str = Field(min_length=1, max_length=20)
    note: str | None = Field(default=None, max_length=500)


class InventoryRow(ApiModel):
    product_id: UUID
    name: str
    sku: str | None
    stock: int
    low_stock_threshold: int
    stock_status: str


class InventoryPage(ApiModel):
    items: list[InventoryRow]
    total: int
    page: int
    total_pages: int
    limit: int


class MovementOut(ApiModel):
    id: UUID
    change: int
    previous_stock: int
    new_stock: int
    reason: str
    note: str | None
    created_by: UUID | None
    order_id: UUID | None
    created_at: datetime


class MovementPage(ApiModel):
    items: list[MovementOut]
    total: int
    page: int
    total_pages: int
    limit: int


class TopProduct(ApiModel):
    product_id: UUID
    name: str
    quantity: int
    revenue: Decimal


class DashboardOrder(ApiModel):
    id: UUID
    order_number: str
    status: str
    total: Decimal
    created_at: datetime


class DashboardProduct(ApiModel):
    id: UUID
    name: str
    price: Decimal


class LowStockRow(ApiModel):
    id: UUID
    name: str
    stock: int
    threshold: int


class DashboardOut(ApiModel):
    sales_today: Decimal
    orders_today: int
    sales_total: Decimal
    orders_by_status: dict[str, int]
    active_products: int
    low_stock_count: int
    top_products: list[TopProduct]
    latest_orders: list[DashboardOrder]
    latest_products: list[DashboardProduct]
    low_stock: list[LowStockRow]
