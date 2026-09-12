"""one saved cart per account

The cart lives in the browser and always will - a guest has no account to hang
one on, and going to the server for every `+` and `-` would make the fastest
part of the site the slowest. This table is the copy that follows a signed-in
shopper between devices: added on a phone at lunch, still there on a laptop in
the evening, and not lost when a browser clears its storage.

One row per person rather than a row per line, because the cart is read and
written whole and never a line at a time. A single `jsonb` document matches how
it is used and keeps the whole cart one round trip away.

No foreign key to `products`: a cart is a note about what someone is thinking of
buying, not a record of anything. An archived or deleted product has to make one
line unavailable, not make the cart unreadable.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "carts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "items",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_carts")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_carts_user_id_users"), ondelete="CASCADE"
        ),
        # One cart per account, enforced here rather than by hoping the service
        # always looks before it inserts.
        sa.UniqueConstraint("user_id", name=op.f("uq_carts_user_id")),
    )


def downgrade() -> None:
    op.drop_table("carts")
