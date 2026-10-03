"""catalog: optional English names, and an English product description

The /en storefront showed every category, brand and product name in Georgian,
because there was nothing else to show. Each now has an optional English name,
and a product an optional English description. The Georgian columns stay as
they are and stay required.

NOT NULL with an empty default, as short_name and description already are: one
"absent" value instead of two, and the storefront falls back to the Georgian
for it. A constant default is a catalogue change on Postgres 11+, not a table
rewrite, and every existing row reads as untranslated.

No backfill of products.search_text: an empty English name adds nothing to it,
so every row is already correct. The admin form rebuilds it on the save that
sets one.

The code before this revision never names these columns, and an INSERT from it
gets the default, so the migration can be applied before that code is replaced.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "categories", sa.Column("name_en", sa.String(150), server_default="", nullable=False)
    )
    op.add_column("brands", sa.Column("name_en", sa.String(150), server_default="", nullable=False))
    op.add_column(
        "products", sa.Column("name_en", sa.String(300), server_default="", nullable=False)
    )
    op.add_column(
        "products", sa.Column("description_en", sa.Text(), server_default="", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("products", "description_en")
    op.drop_column("products", "name_en")
    op.drop_column("brands", "name_en")
    op.drop_column("categories", "name_en")
