"""guest orders: a lookup token, stored as a hash

A guest read their order with its number and the phone given at checkout. The
number is sequential and a phone is known to others, so anyone holding a
shopper's phone could walk a day's numbers and read their name and address.
The lookup now takes a random token issued with the order; this column holds
only its SHA-256, as password_reset_tokens does, so a leaked copy opens
nothing.

Nullable, with no backfill: a signed-in customer's order has no token, and a
token cannot be made for an order already placed - its raw value would have to
reach a browser that is no longer waiting for it. Those guest orders can no
longer be looked up.

No index: the lookup filters on order_number, which is unique, and compares
this column on the one row that finds.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("lookup_token_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "lookup_token_hash")
