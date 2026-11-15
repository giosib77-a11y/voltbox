"""orders.request_hash: tell a retry of a checkout from a different one on the same key

An Idempotency-Key answers a repeated checkout with the order it first made.
Until now the key was the whole comparison: the same key and the same contact
with a different basket (qty 1, then qty 5) came back as the old qty-1 order
under a 201, and the shopper believed they had ordered five.

`request_hash` is the SHA-256 (hex, 64 characters) of the canonical request the
order was placed with - items, customer, payment method (services/order.py,
`request_hash`). A repeat of the key whose hash differs is refused with 409
`IDEMPOTENCY_KEY_REUSED`.

Nullable with no default and no backfill: the request an existing order was
placed with is not recoverable (the items are stored, but the raw customer and
the lines before merging are not), so those orders keep a NULL and a repeat of
their key is compared on the key alone, as before. Only orders placed after
this migration are protected.

No index: the column is read together with the row found by the unique
`idempotency_key` index, never searched. No new table, so no row level
security to enable. Statements are schema-qualified, as the SQL handed to the
Supabase SQL Editor must be.

Downgrade drops the column. Nothing else is touched: no order, item or history
row is deleted; the orders merely go back to being compared on the key alone.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("request_hash", sa.String(length=64), nullable=True),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("orders", "request_hash", schema="public")
