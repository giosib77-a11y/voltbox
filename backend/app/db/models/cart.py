"""შენახული კალათა.

The cart lives in the browser and always will: a guest has no account to hang
one on, and going to the server for every `+` and `-` would make the fastest
part of the site the slowest. This table is the copy that follows a signed-in
shopper between devices - added to a phone at lunch, still there on a laptop in
the evening, and not lost when a browser clears its storage.

One row per person rather than a row per line. The cart is read and written
whole, never a line at a time, so a single `jsonb` document is the shape that
matches how it is used - and it keeps the whole cart one round trip away, which
was the reason it lives in the browser to begin with.

No foreign key to `products`. A cart is a note about what someone is thinking
of buying, not a record of anything; a product that is archived or deleted must
make the line unavailable, not make the cart unreadable. The stored `productId`
is checked against the catalogue when the cart is read, and the price is checked
again at checkout regardless - `services/order.py` never trusts a number that
arrived from a client.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey

#: A basket far past this is not a basket. The limit exists so that a stored
#: document cannot be grown without bound by a client that keeps adding lines.
MAX_CART_ITEMS = 50


class Cart(Base, UUIDPrimaryKey):
    """One saved cart per account."""

    __tablename__ = "carts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    #: `[{"productId": "...", "qty": 2}, ...]` and nothing else. The name, price
    #: and image the browser keeps alongside each line are deliberately absent:
    #: they are a snapshot for drawing the cart quickly, and a stale one a month
    #: later is worse than reading the current values back from the catalogue.
    items: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )
