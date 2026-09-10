"""The admin dashboard.

What it does: one request, one set of SQL aggregates.
Where it fits: GET /admin/dashboard.

Notes: nothing here loads orders into Python to add them up. On a shop with any
history that is the difference between a dashboard and a timeout, and the
numbers would drift from what the orders list shows.

The definitions below are the contract. They are constants rather than prose in
a docstring because "sales" has to mean one thing everywhere.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Order, OrderItem, Product
from app.services.admin_orders import day_bounds, store_tz
from app.services.order_status import counts_by_status

#: Cancelled orders are excluded from every money figure. They were returned to
#: stock, so counting their value as sales would overstate the shop.
EXCLUDED_FROM_SALES = ("cancelled",)

#: How far back "top products" looks.
TOP_PRODUCTS_DAYS = 30
TOP_PRODUCTS_LIMIT = 5
LATEST_ORDERS_LIMIT = 10
LATEST_PRODUCTS_LIMIT = 5


async def build(db: AsyncSession) -> dict[str, Any]:
    """Every dashboard figure, computed in the database."""
    today = datetime.now(store_tz()).date()
    day_start, day_end = day_bounds(today)

    sold = Order.status.notin_(EXCLUDED_FROM_SALES)

    sales_today = await db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            sold, Order.created_at >= day_start, Order.created_at < day_end
        )
    )
    orders_today = await db.scalar(
        select(func.count())
        .select_from(Order)
        .where(sold, Order.created_at >= day_start, Order.created_at < day_end)
    )
    sales_total = await db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(sold))

    active_products = await db.scalar(
        select(func.count())
        .select_from(Product)
        .where(Product.is_active.is_(True), Product.archived_at.is_(None))
    )
    low_stock_count = await db.scalar(
        select(func.count())
        .select_from(Product)
        .where(
            Product.is_active.is_(True),
            Product.archived_at.is_(None),
            Product.stock <= Product.low_stock_threshold,
        )
    )

    since = datetime.now(UTC) - timedelta(days=TOP_PRODUCTS_DAYS)
    top_rows = await db.execute(
        select(
            OrderItem.product_id,
            OrderItem.product_name,
            func.sum(OrderItem.quantity).label("quantity"),
            func.sum(OrderItem.line_total).label("revenue"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(sold, Order.created_at >= since)
        # From the snapshots, not from products: an item sold under an old name
        # still belongs to that sale.
        .group_by(OrderItem.product_id, OrderItem.product_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(TOP_PRODUCTS_LIMIT)
    )

    latest_orders = list(
        (
            await db.scalars(
                select(Order).order_by(Order.created_at.desc()).limit(LATEST_ORDERS_LIMIT)
            )
        )
        .unique()
        .all()
    )
    latest_products = list(
        (
            await db.scalars(
                select(Product)
                .where(Product.archived_at.is_(None))
                .order_by(Product.created_at.desc())
                .limit(LATEST_PRODUCTS_LIMIT)
            )
        )
        .unique()
        .all()
    )
    low_stock = list(
        (
            await db.scalars(
                select(Product)
                .where(
                    Product.is_active.is_(True),
                    Product.archived_at.is_(None),
                    Product.stock <= Product.low_stock_threshold,
                )
                .order_by(Product.stock)
                .limit(TOP_PRODUCTS_LIMIT)
            )
        )
        .unique()
        .all()
    )

    return {
        "sales_today": Decimal(sales_today or 0),
        "orders_today": int(orders_today or 0),
        "sales_total": Decimal(sales_total or 0),
        "orders_by_status": await counts_by_status(db),
        "active_products": int(active_products or 0),
        "low_stock_count": int(low_stock_count or 0),
        "top_products": [
            {
                "product_id": row[0],
                "name": row[1],
                "quantity": int(row[2]),
                "revenue": Decimal(row[3]),
            }
            for row in top_rows
        ],
        "latest_orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "total": order.total,
                "created_at": order.created_at,
            }
            for order in latest_orders
        ],
        "latest_products": [
            {"id": product.id, "name": product.name, "price": product.price}
            for product in latest_products
        ],
        "low_stock": [
            {
                "id": product.id,
                "name": product.name,
                "stock": product.stock,
                "threshold": product.low_stock_threshold,
            }
            for product in low_stock
        ],
    }
