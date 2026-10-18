"""Moving an order into the admin trash and back.

What it does: sets or clears `orders.deleted_at`, and owns how long a trashed
order is kept.
Where it fits: called by app/api/v1/routes/admin/orders.py, which writes the
audit row and commits. The status graph stays in services/order_status.py.
Notes: stock is never touched here - no `adjust_stock`, no
`inventory_movements` row. Both calls lock the row through the state machine's
lock, so a trash racing a status change is serialised and the frozen-status
check in `order_status.transition` sees the committed state. Repeating either
call changes nothing (a double click or a retry), and `deleted_at` keeps its
first value.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Order
from app.services.order_status import lock_order

#: How long a trashed order is kept before it may be purged. The only place the
#: number lives: `purge_at` in the admin summary and the purge both read it.
TRASH_RETENTION = timedelta(days=30)


def purge_at(deleted_at: datetime | None) -> datetime | None:
    """When a trashed order becomes eligible for the purge; None for a live one."""
    return None if deleted_at is None else deleted_at + TRASH_RETENTION


async def trash(db: AsyncSession, order_id: uuid.UUID) -> tuple[Order, bool]:
    """Put the order in the trash. Returns the order and whether anything changed."""
    order = await lock_order(db, order_id)
    if order.deleted_at is not None:
        return order, False
    # The application clock, not `now()`: the database clock is frozen at the
    # start of the transaction, and the same value must be what `purge_at` adds
    # the retention to.
    order.deleted_at = datetime.now(UTC)
    await db.flush()
    return order, True


async def restore(db: AsyncSession, order_id: uuid.UUID) -> tuple[Order, bool]:
    """Take the order out of the trash. Returns the order and whether anything changed."""
    order = await lock_order(db, order_id)
    if order.deleted_at is None:
        return order, False
    order.deleted_at = None
    await db.flush()
    return order, True
