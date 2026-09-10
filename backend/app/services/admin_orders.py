"""Admin order queries.

What it does: the filtered order list and the detail view.
Where it fits: called by app/api/v1/routes/admin/orders.py. Status changes are
not here - they belong to services/order_status.py, the single place that may
write `orders.status`.
Notes: date filters are resolved in the store's timezone. "Today" for a shop in
Tbilisi is not the UTC day, and an order placed at 01:00 belongs to that day.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.db.models import Order, OrderItem
from app.services.order_status import allowed_transitions

DIGITS = re.compile(r"\D+")


def store_tz() -> ZoneInfo:
    return ZoneInfo(settings.store_timezone)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC instants that bracket a business day in the store's timezone.

    Returned as an inclusive start and an exclusive end, so an order at exactly
    midnight belongs to the new day and nothing is counted twice.
    """
    tz = store_tz()
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return start, end


def normalize_phone(value: str) -> str:
    """Strip everything but digits, and drop the country code.

    `+995 555 12 34 56` and `555123456` are the same phone, and an admin will
    type whichever one they are looking at.
    """
    digits = DIGITS.sub("", value)
    if digits.startswith("995") and len(digits) > 9:
        digits = digits[3:]
    return digits


def _conditions(
    *,
    q: str | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []

    if status:
        conditions.append(Order.status == status)

    if date_from:
        conditions.append(Order.created_at >= day_bounds(date_from)[0])
    if date_to:
        # Exclusive upper bound of the last day, so `date_to` is inclusive to a
        # reader and still excludes the following midnight.
        conditions.append(Order.created_at < day_bounds(date_to)[1])

    if q:
        needle = q.strip()
        if needle:
            digits = normalize_phone(needle)
            clauses = [
                Order.order_number.ilike(f"%{needle.upper()}%"),
                Order.guest_email.ilike(f"%{needle}%"),
                Order.customer["firstName"].astext.ilike(f"%{needle}%"),
                Order.customer["lastName"].astext.ilike(f"%{needle}%"),
            ]
            if digits:
                # The stored phone may carry formatting too, so both sides are
                # reduced to digits before comparing.
                stored = func.regexp_replace(
                    func.coalesce(Order.customer["phone"].astext, ""), r"\D", "", "g"
                )
                clauses.append(stored.ilike(f"%{digits}%"))
                clauses.append(func.cast(Order.guest_phone, String).ilike(f"%{digits}%"))
            conditions.append(or_(*clauses))

    return conditions


def _text(value: object) -> str | None:
    """A JSONB value as text, or None for anything that is not a string."""
    return value if isinstance(value, str) and value else None


def _summary(order: Order, item_count: int) -> dict[str, Any]:
    customer = order.customer or {}
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        # `customer` is a JSONB snapshot typed as dict[str, object], so every
        # value has to be narrowed before it can be joined or returned.
        "customer_name": " ".join(
            str(part)
            for part in (customer.get("firstName"), customer.get("lastName"))
            if isinstance(part, str) and part
        )
        or "—",
        "phone": _text(customer.get("phone")) or order.guest_phone,
        "email": _text(customer.get("email")) or order.guest_email,
        "city": _text(customer.get("city")),
        "total": order.total,
        "item_count": item_count,
        "payment_method": order.payment_method,
        "created_at": order.created_at,
    }


async def list_orders(
    db: AsyncSession,
    *,
    page: int,
    limit: int,
    q: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    conditions = _conditions(q=q, status=status, date_from=date_from, date_to=date_to)

    total = await db.scalar(select(func.count()).select_from(Order).where(*conditions))

    stmt = (
        select(Order)
        .where(*conditions)
        .order_by(Order.created_at.desc(), Order.id)
        .limit(limit)
        .offset((page - 1) * limit)
    )
    orders = list((await db.scalars(stmt)).unique().all())

    # Item counts in one grouped query rather than one per order.
    counts: dict[uuid.UUID, int] = {}
    if orders:
        rows = await db.execute(
            select(OrderItem.order_id, func.count().label("hits"))
            .where(OrderItem.order_id.in_([order.id for order in orders]))
            .group_by(OrderItem.order_id)
        )
        counts = {row[0]: int(row[1]) for row in rows}

    total_count = int(total or 0)
    return {
        "items": [_summary(order, counts.get(order.id, 0)) for order in orders],
        "total": total_count,
        "page": page,
        "total_pages": (total_count + limit - 1) // limit if limit else 0,
        "limit": limit,
    }


async def get_order(db: AsyncSession, order_id: uuid.UUID) -> dict[str, Any]:
    stmt = select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    order = (await db.scalars(stmt)).unique().one_or_none()
    if order is None:
        raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")

    customer = order.customer or {}
    return {
        **_summary(order, len(order.items)),
        "customer": customer,
        "shipping_address": order.shipping_address,
        "subtotal": order.subtotal,
        "shipping": order.shipping,
        "currency": order.currency,
        "notes": order.notes,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "product_slug": item.product_slug,
                "image_url": item.image_url,
                "unit_price": item.unit_price,
                "quantity": item.quantity,
                "line_total": item.line_total,
            }
            for item in order.items
        ],
        # The UI must never re-implement the state machine; it renders what the
        # server says is possible.
        "allowed_transitions": allowed_transitions(order.status),
    }


def parse_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(
            "Expected a date in YYYY-MM-DD form",
            code="INVALID_DATE",
            details=[{"field": field, "value": value}],
        ) from exc
