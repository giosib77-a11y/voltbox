"""SQLAlchemy models.

Alembic-ის autogenerate-ს ყველა მოდელი ერთ ადგილას იმპორტირებული სჭირდება,
თორემ ცხრილებს ვერ დაინახავს.
"""

from app.db.models.audit import AdminAuditLog
from app.db.models.catalog import Brand, Category, Product, ProductImage
from app.db.models.inventory import (
    MANUAL_REASONS,
    MOVEMENT_REASONS,
    REASON_CORRECTION,
    REASON_INITIAL,
    REASON_MANUAL,
    REASON_ORDER_CANCELLED,
    REASON_ORDER_PLACED,
    REASON_RESTOCK,
    REASON_RETURN,
    REASONS_REQUIRING_NOTE,
    InventoryMovement,
)
from app.db.models.orders import ORDER_STATUSES, Order, OrderItem, OrderStatusHistory
from app.db.models.users import (
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    ROLES,
    Address,
    RefreshToken,
    User,
)

__all__ = [
    "MANUAL_REASONS",
    "MOVEMENT_REASONS",
    "ORDER_STATUSES",
    "REASONS_REQUIRING_NOTE",
    "REASON_CORRECTION",
    "REASON_INITIAL",
    "REASON_MANUAL",
    "REASON_ORDER_CANCELLED",
    "REASON_ORDER_PLACED",
    "REASON_RESTOCK",
    "REASON_RETURN",
    "ROLES",
    "ROLE_ADMIN",
    "ROLE_CUSTOMER",
    "Address",
    "AdminAuditLog",
    "Brand",
    "Category",
    "InventoryMovement",
    "Order",
    "OrderItem",
    "OrderStatusHistory",
    "Product",
    "ProductImage",
    "RefreshToken",
    "User",
]
