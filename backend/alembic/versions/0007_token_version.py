"""a version an access token has to still match

An access token is a signed statement with a thirty minute life and no way to
take it back. Revoking the refresh tokens stops a session being extended; it
does nothing about the access token already in the thief's hands. Changing a
stolen password therefore left them signed in for the rest of that half hour -
the one moment the owner is certain something is wrong.

`token_version` is embedded in each token as `tv` and compared on every request.
A counter on the user rather than a list of dead token ids, because
`get_current_user` already reads this row: the check costs nothing, where a
deny-list would cost a lookup per request. A counter rather than a "valid from"
instant because `iat` is whole seconds, and a token minted in the same second as
the revocation could not be told from one minted just before it.

Existing rows start at 0. Tokens issued before this migration carry no `tv` at
all and are refused, so everyone signed in at that moment refreshes once.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
