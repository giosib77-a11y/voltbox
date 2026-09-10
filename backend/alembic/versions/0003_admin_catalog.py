"""admin catalog: archiving, the stock ledger and the audit log

Three changes, all additive - nothing existing is altered or dropped:

  products.archived_at   retiring a product is not the same as hiding it.
                         is_active=false is temporary (draft, out of season);
                         archived is permanent. Archiving also sets
                         is_active=false, so storefront queries need no change.

  inventory_movements    one row per change to products.stock, with the value
                         before and after. Without it, "why is stock 3?" has no
                         answer. A backfill writes one `initial` row per product
                         that already has stock, so the ledger reconciles with
                         current stock from day one instead of starting at a
                         number nobody can explain.

  admin_audit_log        who changed what, and from what to what.

low_stock_threshold is deliberately NOT added here: it already exists with
server_default 3, matching the frontend's LOW_STOCK_THRESHOLD.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MOVEMENT_REASONS = (
    "initial",
    "restock",
    "manual_adjustment",
    "order_placed",
    "order_cancelled",
    "return",
    "correction",
)


def upgrade() -> None:
    op.add_column("products", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "inventory_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("change", sa.Integer(), nullable=False),
        sa.Column("previous_stock", sa.Integer(), nullable=False),
        sa.Column("new_stock", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            # clock_timestamp(), not now(): now() returns the transaction start
            # time, so rows written together would share a timestamp and the
            # history could not be ordered. Checkout writes one movement per
            # line item inside a single transaction, so that is the normal case.
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        # A movement of zero explains nothing and would only add noise.
        sa.CheckConstraint("change <> 0", name="movement_change_not_zero"),
        # The ledger must be arithmetically consistent at the database level:
        # an application bug cannot write a row whose numbers do not add up.
        sa.CheckConstraint(
            "new_stock = previous_stock + change AND new_stock >= 0",
            name="movement_arithmetic_holds",
        ),
        sa.CheckConstraint(
            "reason IN ('initial','restock','manual_adjustment','order_placed',"
            "'order_cancelled','return','correction')",
            name="movement_reason_allowed",
        ),
    )
    op.execute(
        "CREATE INDEX ix_inventory_movements_product_created "
        "ON inventory_movements (product_id, created_at DESC)"
    )

    # Backfill: one `initial` row per product that already holds stock.
    # gen_random_uuid() comes from pgcrypto, which Postgres 13+ has built in.
    op.execute(
        """
        INSERT INTO inventory_movements
            (id, product_id, change, previous_stock, new_stock, reason, note, created_at)
        SELECT gen_random_uuid(), id, stock, 0, stock, 'initial',
               'Backfilled when the stock ledger was introduced', now()
        FROM products
        WHERE stock > 0
        """
    )

    op.create_table(
        "admin_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # SET NULL, not CASCADE: deleting a user must not erase the record of
        # what they changed.
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column(
            "changes",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            # clock_timestamp(), not now(): now() returns the transaction start
            # time, so rows written together would share a timestamp and the
            # history could not be ordered. Checkout writes one movement per
            # line item inside a single transaction, so that is the normal case.
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
    )
    op.create_index("ix_admin_audit_log_entity", "admin_audit_log", ["entity_type", "entity_id"])
    op.execute("CREATE INDEX ix_admin_audit_log_created_at ON admin_audit_log (created_at DESC)")

    # RLS stays consistent with every other table: enabled with no policies, so
    # a direct connection that is not the service role reads nothing.
    for table in ("inventory_movements", "admin_audit_log"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_admin_audit_log_created_at", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_entity", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")

    op.drop_index("ix_inventory_movements_product_created", table_name="inventory_movements")
    op.drop_table("inventory_movements")

    op.drop_column("products", "archived_at")
