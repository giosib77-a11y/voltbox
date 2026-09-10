"""Stock movement ledger.

What it does: one row per change to `products.stock`, with the value before and
after, so current stock can always be explained.
Where it fits: written only by app/services/inventory.py - checkout, admin
adjustments and order cancellations all go through the same function.
Notes: reasons are VARCHAR + CHECK rather than a native PG enum. Adding a reason
later is then an ordinary migration instead of ALTER TYPE, which cannot run
inside a transaction with other statements.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey

# Reasons a stock level can change. The manual ones are what an admin may pick;
# the rest are written by the system and must never be selectable in a form.
REASON_INITIAL = "initial"
REASON_RESTOCK = "restock"
REASON_MANUAL = "manual_adjustment"
REASON_ORDER_PLACED = "order_placed"
REASON_ORDER_CANCELLED = "order_cancelled"
REASON_RETURN = "return"
REASON_CORRECTION = "correction"

MOVEMENT_REASONS = (
    REASON_INITIAL,
    REASON_RESTOCK,
    REASON_MANUAL,
    REASON_ORDER_PLACED,
    REASON_ORDER_CANCELLED,
    REASON_RETURN,
    REASON_CORRECTION,
)

#: Reasons an administrator may choose in the adjustment form.
MANUAL_REASONS = (REASON_RESTOCK, REASON_MANUAL, REASON_RETURN, REASON_CORRECTION)

#: Reasons that require the admin to explain themselves.
REASONS_REQUIRING_NOTE = (REASON_MANUAL, REASON_CORRECTION)


class InventoryMovement(UUIDPrimaryKey, Base):
    __tablename__ = "inventory_movements"

    product_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    change: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    new_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    # NULL means the system did it (checkout), not a person.
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )

    # A ledger row is immutable, so it gets created_at only - the Timestamps
    # mixin would add an updated_at that must never change.
    #
    # clock_timestamp(), not now(): now() returns the transaction start time, so
    # every movement written inside one transaction would carry an identical
    # timestamp and the history could not be ordered. Checkout writes one row
    # per line item in a single transaction, so that is the normal case, not an
    # edge case.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("clock_timestamp()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint("change <> 0", name="movement_change_not_zero"),
        CheckConstraint(
            "new_stock = previous_stock + change AND new_stock >= 0",
            name="movement_arithmetic_holds",
        ),
        CheckConstraint(
            "reason IN ('initial','restock','manual_adjustment','order_placed',"
            "'order_cancelled','return','correction')",
            name="movement_reason_allowed",
        ),
        Index("ix_inventory_movements_product_created", "product_id", text("created_at DESC")),
    )
