"""Stock changes - the single write path for products.stock.

What it does: `adjust_stock` locks a product row, refuses a result below zero,
writes the new value and records one inventory_movements row, all inside the
caller's transaction.
Where it fits: checkout, admin adjustments and order cancellations all call it.
Nothing else may write products.stock.

Why one function: the movement ledger is only trustworthy if it is complete. A
single UPDATE somewhere else leaves a gap that nobody notices until the numbers
are questioned months later, and by then the history cannot be reconstructed.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import (
    MANUAL_REASONS,
    MOVEMENT_REASONS,
    REASONS_REQUIRING_NOTE,
    InventoryMovement,
    Product,
)


async def adjust_stock(
    db: AsyncSession,
    product_id: uuid.UUID,
    change: int,
    reason: str,
    *,
    actor_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    note: str | None = None,
) -> int:
    """Apply a stock delta and record it. Returns the new stock level.

    Does not commit - the caller owns the transaction, so a stock change and the
    order (or audit row) that caused it either both land or neither does.

    `actor_id` is None for system changes such as checkout.
    """
    if change == 0:
        raise ValidationError("Stock change must not be zero", code="EMPTY_ADJUSTMENT")
    if reason not in MOVEMENT_REASONS:
        raise ValidationError(f"Unknown movement reason: {reason}", code="UNKNOWN_REASON")

    # Only the column is selected: `Product.category` and `.brand` are
    # lazy="joined" and Postgres refuses FOR UPDATE on the nullable side of an
    # outer join. Re-locking a row the caller already holds is free.
    previous = await db.scalar(
        select(Product.stock).where(Product.id == product_id).with_for_update()
    )
    if previous is None:
        raise NotFoundError(
            "Product not found", code="PRODUCT_NOT_FOUND", details={"productId": str(product_id)}
        )

    new_stock = previous + change
    if new_stock < 0:
        raise ConflictError(
            "Not enough stock",
            code="INSUFFICIENT_STOCK",
            details={
                "productId": str(product_id),
                "requested": abs(change),
                "available": previous,
            },
        )

    await db.execute(update(Product).where(Product.id == product_id).values(stock=new_stock))
    db.add(
        InventoryMovement(
            product_id=product_id,
            change=change,
            previous_stock=previous,
            new_stock=new_stock,
            reason=reason,
            note=note,
            created_by=actor_id,
            order_id=order_id,
        )
    )
    await db.flush()
    return new_stock


def validate_manual_adjustment(reason: str, note: str | None) -> None:
    """Rules that apply only to an adjustment an administrator types in.

    System reasons (order_placed, order_cancelled, initial) are rejected here:
    letting an admin write one by hand would corrupt the meaning of the ledger.
    """
    if reason not in MANUAL_REASONS:
        raise ValidationError(
            "This reason cannot be selected manually",
            code="REASON_NOT_MANUAL",
            details={"allowed": list(MANUAL_REASONS)},
        )
    if reason in REASONS_REQUIRING_NOTE and not (note or "").strip():
        raise ValidationError(
            "A note is required for this reason",
            code="NOTE_REQUIRED",
            details=[{"field": "note", "reason": reason}],
        )


async def movement_history(
    db: AsyncSession, product_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[InventoryMovement], int]:
    """One page of a product's ledger, newest first, plus the total count."""
    total = await db.scalar(
        select(func.count())
        .select_from(InventoryMovement)
        .where(InventoryMovement.product_id == product_id)
    )
    stmt = (
        select(InventoryMovement)
        .where(InventoryMovement.product_id == product_id)
        .order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list((await db.scalars(stmt)).all())
    return rows, int(total or 0)


def stock_status(stock: int, threshold: int) -> str:
    """`out` / `low` / `ok` - the same wording the admin UI badges use."""
    if stock <= 0:
        return "out"
    if stock <= threshold:
        return "low"
    return "ok"


__all__ = [
    "adjust_stock",
    "movement_history",
    "stock_status",
    "validate_manual_adjustment",
]
