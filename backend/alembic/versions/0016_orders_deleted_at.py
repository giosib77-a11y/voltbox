"""orders.deleted_at: the admin order trash

An admin can move an order to a trash, restore it, or delete it for good. The
trash is a state of the order and not a second table: restoring has to bring
back the order exactly as it was - items, status history, stock accounting -
and a row that never moved cannot lose any of that.

`deleted_at` NULL is a live order. A timestamp is the moment it went to the
trash; the retention job hard-deletes an order 30 days after it
(services/order_trash.py). Nullable with no default and no backfill: every
order that exists now stays live.

The index is partial. Almost every row has deleted_at NULL and nothing looks
those up through this column; the two readers - the trash list and the
retention sweep - want only the rows with a timestamp, so the index holds only
those and stays as small as the trash is. It is not used for the live-order
filter (`deleted_at IS NULL`), which is the rest of the table anyway.

No new table, so no row level security to enable here. Statements are
schema-qualified, as the SQL handed to the Supabase SQL Editor must be.

Downgrade drops the column and the index. Every order that is in the trash
becomes a live order again - the trash state is lost, and the orders will show
in the admin list, the customer's history and the dashboard. Nothing else is
touched: no order, item or history row is deleted, and stock is not changed.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="public",
    )
    op.create_index(
        "ix_orders_deleted_at",
        "orders",
        ["deleted_at"],
        schema="public",
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_orders_deleted_at", table_name="orders", schema="public")
    op.drop_column("orders", "deleted_at", schema="public")
