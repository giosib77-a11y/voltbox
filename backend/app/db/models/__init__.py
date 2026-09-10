"""SQLAlchemy models.

Alembic-ის autogenerate-ს ყველა მოდელი ერთ ადგილას იმპორტირებული სჭირდება,
თორემ ცხრილებს ვერ დაინახავს.
"""

from app.db.models.catalog import Brand, Category, Product, ProductImage
from app.db.models.orders import ORDER_STATUSES, Order, OrderItem
from app.db.models.users import (
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    ROLES,
    Address,
    RefreshToken,
    User,
)

__all__ = [
    "ORDER_STATUSES",
    "ROLES",
    "ROLE_ADMIN",
    "ROLE_CUSTOMER",
    "Address",
    "Brand",
    "Category",
    "Order",
    "OrderItem",
    "Product",
    "ProductImage",
    "RefreshToken",
    "User",
]
