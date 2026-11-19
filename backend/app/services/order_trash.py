"""Moving an order into the admin trash and back, and deleting it for good.

What it does: sets or clears `orders.deleted_at`, owns how long a trashed
order is kept, and hard-deletes a trashed order - by hand (`delete_forever`) or
when the retention has run out (`purge_expired`).
Where it fits: called by app/api/v1/routes/admin/orders.py, which writes the
audit row for trash and restore and commits. The two deletes write their own
`order.purge` row, because the row they delete is the only other record of what
happened. The status graph stays in services/order_status.py.
Notes: stock is never touched here - no `adjust_stock`, no
`inventory_movements` row - and that is why only an order in a final status
(`order_status.FINAL_STATUSES`: cancelled, delivered) may be trashed or deleted,
by hand or by the purge. An order's stock comes back only on a transition to
`cancelled`, and a trashed order cannot make one; trashing or purging an active
order would therefore lose its stock for good (A-116). An active order is
refused with 409 `ORDER_STILL_ACTIVE` ("cancel it first"), and the automatic
purge skips an expired active order (a row trashed before this rule) instead of
deleting it. What still holds: `restore` has no status restriction, so such a
legacy order can be restored, cancelled (stock returns), then trashed again.
Trash, restore and `delete_forever` lock the row
through the state machine's lock, so a trash racing a status change is
serialised: the status checked here and the frozen-status check in
`order_status.transition` see the committed state. Repeating trash or restore
changes nothing (a double click or a retry, even for an order whose status would
not allow a fresh trash), and `deleted_at` keeps its first value. The deletes are Core
statements, so the database does the cascading: items and status history go
with the order (ON DELETE CASCADE) and `inventory_movements.order_id` becomes
NULL (ON DELETE SET NULL); the ORM never loads or rewrites those rows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.db.models import Order
from app.services import audit
from app.services.order_status import FINAL_STATUSES, is_final, lock_order

#: How long a trashed order is kept before it may be purged. The only place the
#: number lives: `purge_at` in the admin summary and the purge both read it.
TRASH_RETENTION = timedelta(days=30)


def purge_at(deleted_at: datetime | None, status: str) -> datetime | None:
    """When a trashed order becomes eligible for the purge.

    None for a live order, and for a trashed order that is still active (trashed
    before A-116): the purge skips it, so a date would promise a deletion that
    never comes. Restore and cancel it first.
    """
    if deleted_at is None or not is_final(status):
        return None
    return deleted_at + TRASH_RETENTION


def _require_final_status(order: Order) -> None:
    """Refuse an order whose stock has not come back yet. Needs the row locked."""
    if not is_final(order.status):
        raise ConflictError(
            "Cancel the order first - that returns its stock",
            code="ORDER_STILL_ACTIVE",
            details={"status": order.status},
        )


async def trash(db: AsyncSession, order_id: uuid.UUID) -> tuple[Order, bool]:
    """Put an order in a final status in the trash.

    Returns the order and whether anything changed; an order already in the
    trash comes back unchanged. An active order is 409 `ORDER_STILL_ACTIVE`.
    """
    order = await lock_order(db, order_id)
    if order.deleted_at is not None:
        return order, False
    _require_final_status(order)
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


async def _record_purge(
    db: AsyncSession,
    *,
    order_id: uuid.UUID,
    order_number: str,
    status: str,
    total: Decimal,
    actor_id: uuid.UUID | None,
    automatic: bool,
    ip: str | None = None,
) -> None:
    # The only record of the order once it is gone, so it carries what finds it
    # again in a support conversation (number, status, total) and nothing about
    # the customer: no name, phone, email or address.
    await audit.record(
        db,
        actor_id=actor_id,
        action="order.purge",
        entity_type="order",
        entity_id=str(order_id),
        changes={
            "orderNumber": order_number,
            "status": status,
            "total": total,
            "automatic": automatic,
        },
        ip=ip,
    )


async def delete_forever(
    db: AsyncSession, order_id: uuid.UUID, *, actor_id: uuid.UUID, ip: str | None = None
) -> None:
    """Hard-delete an order that is in the trash. The caller commits.

    A live order is `ORDER_NOT_IN_TRASH` whatever its status; a trashed order
    that is still active (trashed before the status rule) is `ORDER_STILL_ACTIVE`.
    """
    order = await lock_order(db, order_id)
    if order.deleted_at is None:
        raise ConflictError(
            "Only an order in the trash can be deleted for good",
            code="ORDER_NOT_IN_TRASH",
        )
    _require_final_status(order)
    await _record_purge(
        db,
        order_id=order.id,
        order_number=order.order_number,
        status=order.status,
        total=order.total,
        actor_id=actor_id,
        automatic=False,
        ip=ip,
    )
    # Core delete: the ORM's own `session.delete` would walk `Order.items`
    # (cascade="all, delete-orphan") and issue a DELETE per item that the
    # database's ON DELETE CASCADE already does. The default synchronize_session
    # drops the matched instance from the session.
    await db.execute(delete(Order).where(Order.id == order_id))


async def purge_expired(db: AsyncSession) -> int:
    """Hard-delete every final-status order trashed more than `TRASH_RETENTION` ago.

    An expired order that is still active is left in the trash (no deletion, no
    audit row): deleting it would lose its stock. Returns how many went. The
    caller commits; a call that finds nothing writes nothing. One statement does
    the whole sweep, and the cutoff is the application clock - the same one
    `trash` writes `deleted_at` with, so the day-30 boundary is not split between
    two clocks. A row that a concurrent restore holds is waited for, and once it
    commits the statement re-checks its condition on that row (READ COMMITTED): a
    restored order has no `deleted_at` any more and is left alone.
    """
    cutoff = datetime.now(UTC) - TRASH_RETENTION
    rows = (
        await db.execute(
            delete(Order)
            .where(Order.deleted_at < cutoff, Order.status.in_(sorted(FINAL_STATUSES)))
            .returning(Order.id, Order.order_number, Order.status, Order.total)
        )
    ).all()
    for row in rows:
        await _record_purge(
            db,
            order_id=row.id,
            order_number=row.order_number,
            status=row.status,
            total=row.total,
            actor_id=None,
            automatic=True,
        )
    return len(rows)
