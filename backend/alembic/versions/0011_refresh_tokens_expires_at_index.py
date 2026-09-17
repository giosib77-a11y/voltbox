"""index refresh_tokens.expires_at, for the retention prune

Every refresh writes a row and nothing used to delete one, so the table grew with
every session for as long as the shop ran. scripts/prune_refresh_tokens.py now
removes rows a week past their expiry, and it finds them with a single condition:

  expires_at < now() - interval '7 days'

Without this index that is a scan of the whole table, every day, on a table
whose only other indexes are for looking a token up by what it is.

A B-tree, not BRIN. BRIN suits a column that follows insertion order, which
expires_at does at first, but the prune keeps deleting the oldest rows and new
ones fill the space it frees. The physical order stops matching the values, and
a BRIN index stops being able to skip anything.

Not CONCURRENTLY. Alembic runs each migration inside a transaction, and the SQL
handed to the Supabase SQL Editor is wrapped in BEGIN/COMMIT - CONCURRENTLY is
refused in both. A plain build holds writes to refresh_tokens for as long as it
takes to index a table this size, which is a moment.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
