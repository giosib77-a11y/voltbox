"""add search_text column

წინასწარ ნორმალიზებული საძებნი ტექსტი. GENERATED სვეტად ვერ გავაკეთებთ, რადგან
შიგთავსი სხვა ცხრილებზეც (brands, categories) არის დამოკიდებული — Postgres-ის
generated column მხოლოდ იმავე row-ის სვეტებს ხედავს. ამიტომ აპლიკაცია წერს.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("search_text", sa.Text(), server_default="", nullable=False),
    )
    op.execute(
        "CREATE INDEX ix_products_search_text_trgm ON products USING gin (search_text gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_products_search_text_trgm", table_name="products")
    op.drop_column("products", "search_text")
