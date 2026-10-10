"""row level security on the two tables no earlier revision covered

Every table here is read and written by the backend alone, and Supabase's Data
API is public: a table in `public` without row level security is readable and
writable with the project's anon key. The earlier revisions turn it on table by
table (0001, 0003, 0004, 0012); `carts` (0009) was created without it, and
`alembic_version`, which Alembic makes itself, never had it.

Enabled with no policy, as on every other table: the backend's role is not
subject to it, anyone else reads nothing. FORCE is not added - 0003 and 0004 did
without it as well, and it changes nothing for a role that bypasses RLS.

The Supabase advisor already shows RLS on both tables of the live database, so
there this revision changes nothing. It is for the next database built from the
migrations alone: a new environment, or a rebuild after a disaster.
tests/test_schema.py fails if any table in `public` is left without it.

Statements are schema-qualified: Supabase ships its own `auth.refresh_tokens`
and the habit of qualifying matters more than it does for these two names.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("carts", "alembic_version")


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
