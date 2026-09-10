"""order status history and dashboard indexes

Two changes:

  order_status_history   who moved an order between statuses, when and why.
                         Separate from admin_audit_log because an order's
                         timeline is rendered in the UI, and keeping two records
                         of one event means they eventually disagree.

  orders indexes         the dashboard groups by status and filters by
                         created_at on every load. Without these, both are
                         sequential scans that grow with the order table.

A backfill writes one 'pending' history row per existing order, so every order
has a starting point in its timeline rather than an empty panel.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(20), nullable=False),
        sa.Column("to_status", sa.String(20), nullable=False),
        # SET NULL, not CASCADE: deleting the account must not erase what it did.
        sa.Column(
            "changed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            # clock_timestamp(), not now(): several transitions can land in one
            # transaction and must stay orderable.
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
    )
    op.execute(
        "CREATE INDEX ix_order_status_history_order ON order_status_history (order_id, created_at)"
    )

    op.execute(
        """
        INSERT INTO order_status_history (id, order_id, from_status, to_status, note, created_at)
        SELECT gen_random_uuid(), id, 'pending', 'pending',
               'Backfilled when the status timeline was introduced', created_at
        FROM orders
        """
    )

    op.execute("CREATE INDEX ix_orders_status ON orders (status)")
    op.execute("CREATE INDEX ix_orders_created_at ON orders (created_at DESC)")

    op.execute("ALTER TABLE order_status_history ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_orders_created_at", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_order_status_history_order", table_name="order_status_history")
    op.drop_table("order_status_history")
