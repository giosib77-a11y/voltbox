"""password reset links: one outstanding per account, stored as a hash

A shopper who forgot their password asks for a link by email. The link carries
a random token; this table holds only its SHA-256, the way refresh_tokens does,
so a leaked copy of the table opens nothing.

The account is the primary key, not a column beside one. A new request replaces
the previous token, so only the newest email's link works, and the table can
never hold more rows than there are accounts - nothing has to prune it. Using a
link deletes its row, which is what makes it single-use.

RLS is enabled and forced with no policy, as on refresh_tokens (0001): the API
connects as a role that bypasses it, and any other role that reaches the table
through Supabase's REST endpoint reads nothing.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_password_reset_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_password_reset_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.execute("ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE password_reset_tokens FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
