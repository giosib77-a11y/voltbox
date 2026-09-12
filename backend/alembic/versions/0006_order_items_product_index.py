"""index order_items.product_id

Postgres builds an index for the *referenced* side of a foreign key and leaves
the referencing side alone, so `order_items.product_id` had none. Two things
scan the table because of it:

  admin_product.delete_product   counts the orders that block a delete, so the
                                 admin is told "12 orders" instead of seeing a
                                 foreign-key error.

  the RESTRICT check             Postgres runs its own lookup for the same
                                 column when the DELETE is issued.

Measured on 200k rows with 3000 distinct products: 13.6 ms without the index,
1.25 ms with it - and delete_product pays it twice.

`order_items` grows with every line of every order and nothing ever prunes it,
so this is the one foreign key here that is worth an index. The others point at
`users` and `orders`, which the application never deletes (customers are
deactivated through `is_active`), or at `categories`, which is small enough that
a scan wins.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_order_items_product_id", table_name="order_items")
