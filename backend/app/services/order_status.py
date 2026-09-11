"""The order status state machine.

What it does: defines which status may follow which, and applies a transition
with its side effects.
Where it fits: the single place a status changes. No endpoint writes
`orders.status` directly.

Why one table: an allowed-transition rule spread across endpoints drifts. Here
the graph is data, the API can hand the UI the allowed moves, and the tests can
enumerate every (from, to) pair exhaustively.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import REASON_ORDER_CANCELLED, Order, OrderStatusHistory
from app.services.inventory import adjust_stock

#: The whole graph. Terminal states map to an empty tuple rather than being
#: absent, so "unknown status" and "nowhere to go" stay distinguishable.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "pending": ("confirmed", "cancelled"),
    "confirmed": ("processing", "cancelled"),
    "processing": ("shipped", "cancelled"),
    "shipped": ("delivered",),
    "delivered": (),
    "cancelled": (),
}

#: Georgian labels for the admin UI, kept next to the graph they describe.
STATUS_LABELS = {
    "pending": "მიღებული",
    "confirmed": "დადასტურებული",
    "processing": "მუშავდება",
    "shipped": "გაგზავნილი",
    "delivered": "მიწოდებული",
    "cancelled": "გაუქმებული",
}


def allowed_transitions(status: str) -> list[str]:
    """Where an order in this status may go next."""
    return list(TRANSITIONS.get(status, ()))


async def _lock_order(db: AsyncSession, order_id: uuid.UUID) -> Order:
    """Lock the order row before reading its status.

    Without this, two admins clicking Cancel at the same time would both read
    `pending`, both pass the check and both return the stock.
    """
    locked = await db.scalar(select(Order.id).where(Order.id == order_id).with_for_update())
    if locked is None:
        raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")
    # populate_existing: if this session already holds the order, SQLAlchemy
    # would hand back the instance it has, with the status it read before the
    # lock was granted - so the check would run against a stale value and the
    # lock would have bought nothing.
    order = await db.scalar(
        select(Order).where(Order.id == order_id).execution_options(populate_existing=True)
    )
    if order is None:  # pragma: no cover - the lock above already proved it exists
        raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")
    return order


async def transition(
    db: AsyncSession,
    order_id: uuid.UUID,
    to_status: str,
    *,
    actor_id: uuid.UUID | None,
    note: str | None = None,
) -> Order:
    """Move an order to `to_status`, applying side effects and history."""
    if to_status not in TRANSITIONS:
        raise ValidationError(
            f"Unknown status: {to_status}",
            code="UNKNOWN_STATUS",
            details={"allowed": sorted(TRANSITIONS)},
        )

    order = await _lock_order(db, order_id)
    from_status = order.status

    if to_status not in TRANSITIONS[from_status]:
        raise ConflictError(
            f"An order cannot go from {from_status} to {to_status}",
            code="INVALID_TRANSITION",
            details={
                "from": from_status,
                "to": to_status,
                "allowed": allowed_transitions(from_status),
            },
        )

    if to_status == "cancelled":
        # Ascending product id, the same rule checkout follows, so a cancellation
        # racing an order cannot deadlock against it.
        for item in sorted(order.items, key=lambda i: i.product_id):
            await adjust_stock(
                db,
                item.product_id,
                item.quantity,
                REASON_ORDER_CANCELLED,
                actor_id=actor_id,
                order_id=order.id,
            )

    order.status = to_status
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=from_status,
            to_status=to_status,
            changed_by=actor_id,
            note=(note or "").strip() or None,
        )
    )
    await db.flush()
    return order


async def history(db: AsyncSession, order_id: uuid.UUID) -> list[OrderStatusHistory]:
    stmt = (
        select(OrderStatusHistory)
        .where(OrderStatusHistory.order_id == order_id)
        .order_by(OrderStatusHistory.created_at, OrderStatusHistory.id)
    )
    return list((await db.scalars(stmt)).all())


async def counts_by_status(db: AsyncSession) -> dict[str, int]:
    """One grouped query, not one COUNT per status."""
    rows = await db.execute(select(Order.status, func.count().label("hits")).group_by(Order.status))
    found: dict[str, Any] = {row[0]: int(row[1]) for row in rows}
    # Every status appears, including the ones with no orders - a missing key
    # would render as a gap in the dashboard instead of a zero.
    return {status: found.get(status, 0) for status in TRANSITIONS}
