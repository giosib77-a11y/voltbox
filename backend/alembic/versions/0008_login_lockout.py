"""count failed sign-ins on the account

The rate limit in front of `/auth/login` counts per IP address, and a thousand
rented proxies is a thousand times the allowance against one email. Counting on
the account closes that: every attempt against an account has the account in
common, and nothing else.

Once the count crosses the threshold the account is refused for a while, before
the password is hashed. That also takes the Argon2 cost out of an attacker's
reach - it is deliberately expensive, and the expense should fall on people
signing in rather than on whoever is guessing.

The cost is that someone who knows an email can hold that account shut by
failing on purpose. It is bounded: the lock lifts on its own, and an existing
session keeps working because refreshing does not go through here.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
