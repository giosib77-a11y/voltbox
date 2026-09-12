"""only the payment methods this shop offers

`payment_method` was a free 32-character string all the way from the request
body to the admin panel. Both real values mean "on delivery" - there is no
online payment - so nothing here moves money and a made-up value could not steal
anything.

What it could do is arrive in the order list reading "already paid" beside an
order that is not, which is a courier handing goods over for nothing. `status`
has had an enum since the first migration; this is the same idea applied to the
other field an operator acts on.

The schema refuses it too. This constraint is the half that still holds when the
next way of creating an order is written.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Written out rather than interpolated from a constant. There is nothing
#: user-supplied here, but a migration that builds SQL with an f-string is the
#: shape a real injection has, and it is not worth teaching the linter to ignore.
ALLOWED = "payment_method IN ('cash','card_on_delivery')"


def upgrade() -> None:
    # Anything already stored that is not one of the two becomes 'cash': these
    # orders are all paid on delivery whatever the column says, and refusing to
    # migrate over a string nobody chose on purpose would be worse.
    op.execute(
        "UPDATE orders SET payment_method = 'cash' "
        "WHERE payment_method NOT IN ('cash','card_on_delivery')"
    )
    op.create_check_constraint("payment_method_allowed", "orders", ALLOWED)


def downgrade() -> None:
    op.drop_constraint("payment_method_allowed", "orders", type_="check")
