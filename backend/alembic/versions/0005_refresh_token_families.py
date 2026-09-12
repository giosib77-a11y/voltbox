"""refresh token families, so reuse can be acted on

Rotation on its own only *notices* that a spent token came back; without a way
to say which session it belonged to, the only responses were to ignore it or to
sign the person out of every device they own. `family_id` ties one login to
every token rotated out of it, so the answer can be "end that session".

Existing rows each become a family of one. That is right rather than merely
convenient: nothing recorded which token replaced which, so grouping them any
other way would be a guess, and a wrong guess here revokes sessions that were
never in danger.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable first: the column is NOT NULL in the end, and adding it that way
    # in one step fails on any table that already holds rows.
    op.add_column("refresh_tokens", sa.Column("family_id", sa.UUID(), nullable=True))
    op.execute("UPDATE refresh_tokens SET family_id = id WHERE family_id IS NULL")
    op.alter_column("refresh_tokens", "family_id", nullable=False)
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "family_id")
