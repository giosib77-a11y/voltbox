"""შენახული კალათა — წაკითხვა, ჩაწერა და შერწყმა შესვლისას.

What it does: keeps one cart per account and resolves it against the catalogue
on the way out, so the client always receives current prices and stock.
Where it fits: the browser stays the source of truth while shopping - every `+`
and `-` is local and instant - and this is the copy that survives a different
device or a cleared browser.

Two decisions worth stating, because both could reasonably have gone the other
way:

**Merging takes the larger quantity, not the sum.** Someone who put two cables
in on a phone and two on a laptop meant to buy two, not four - the second basket
is usually the same intention expressed again, not an addition to it. Summing
silently doubles an order at the moment a person is least likely to re-read it.

**What is stored is the product id and a quantity, nothing else.** The browser
keeps a snapshot of the name, price and image so it can draw the cart without
waiting; storing that here would mean serving a month-old price from the server
as though it were current. Prices are read back from the catalogue on every
load, and checked again at checkout - `services/order.py` has never trusted a
number that arrived from a client.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ValidationError
from app.db.models import MAX_CART_ITEMS, Cart, Product

#: Matches the per-line cap the order schema enforces, so a cart can never hold
#: a quantity that checkout would refuse.
MAX_QUANTITY = 99


def _clean(items: list[dict[str, Any]] | None) -> dict[uuid.UUID, int]:
    """Whatever arrived, reduced to `{product id: quantity}`.

    Anything unreadable is dropped rather than refused. A cart is not a form:
    one line the client sent in a shape we do not recognise should not cost the
    shopper the rest of the basket.
    """
    cleaned: dict[uuid.UUID, int] = {}
    for entry in items or []:
        if not isinstance(entry, dict):
            continue
        try:
            product_id = uuid.UUID(str(entry.get("productId")))
        except (ValueError, TypeError, AttributeError):
            continue
        try:
            quantity = int(entry.get("qty", 0))
        except (ValueError, TypeError):
            continue
        if quantity <= 0:
            continue
        # Later lines for one product replace earlier ones rather than adding,
        # so a client that sent the same id twice cannot double its own basket.
        cleaned[product_id] = min(quantity, MAX_QUANTITY)
    return cleaned


async def _resolve(db: AsyncSession, wanted: dict[uuid.UUID, int]) -> list[dict[str, Any]]:
    """Turn ids and quantities into lines the storefront can draw.

    Everything but the quantity is read from the catalogue: a saved cart is a
    list of intentions, and the price beside each one has to be today's.
    """
    if not wanted:
        return []

    products = (
        await db.scalars(
            select(Product).where(Product.id.in_(wanted)).options(selectinload(Product.images))
        )
    ).all()

    lines = []
    for product in products:
        # A product that has gone away since is simply not in the answer. The
        # cart survives it; the line does not.
        if product.archived_at is not None or not product.is_active:
            continue
        primary = next(
            (
                image.url
                for image in sorted(product.images, key=lambda i: (not i.is_primary, i.position))
            ),
            "",
        )
        lines.append(
            {
                "productId": str(product.id),
                "qty": min(wanted[product.id], MAX_QUANTITY),
                "snapshot": {
                    "name": product.name,
                    "slug": product.slug,
                    "image": primary,
                    "price": str(product.price),
                    "oldPrice": str(product.old_price) if product.old_price else None,
                    "stock": product.stock,
                },
            }
        )
    return lines


async def get_cart(db: AsyncSession, user_id: uuid.UUID) -> list[dict[str, Any]]:
    """The saved cart, priced from today's catalogue."""
    stored = await db.scalar(select(Cart).where(Cart.user_id == user_id))
    return await _resolve(db, _clean(stored.items if stored else []))


async def _store(db: AsyncSession, user_id: uuid.UUID, wanted: dict[uuid.UUID, int]) -> None:
    """Write the cart, creating the row if this account has never had one.

    An upsert rather than a read-then-write: two tabs saving at once would
    otherwise both find nothing and both insert, and the unique constraint would
    turn the second one into a 500.
    """
    payload = [{"productId": str(pid), "qty": qty} for pid, qty in wanted.items()]
    statement = pg_insert(Cart).values(user_id=user_id, items=payload)
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[Cart.user_id],
            # Subscripted, not `excluded.items`: `excluded` is a column
            # collection and `.items` reaches its `items()` method instead of
            # the column of that name. The statement then compiles and fails at
            # execution with "Object of type method is not JSON serializable".
            set_={"items": statement.excluded["items"]},
        )
    )


async def save_cart(
    db: AsyncSession, user_id: uuid.UUID, items: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Replace the saved cart with what the browser is holding."""
    wanted = _clean(items)
    if len(wanted) > MAX_CART_ITEMS:
        raise ValidationError(
            f"A cart cannot hold more than {MAX_CART_ITEMS} different products",
            code="CART_TOO_LARGE",
            details={"limit": MAX_CART_ITEMS, "received": len(wanted)},
        )
    await _store(db, user_id, wanted)
    return await _resolve(db, wanted)


async def merge_cart(
    db: AsyncSession, user_id: uuid.UUID, items: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Fold the browser's cart into the saved one, on signing in.

    The larger quantity wins rather than the sum. Two cables added on a phone
    and two on a laptop is one person meaning two, not four - the second basket
    is the same intention expressed again far more often than it is an addition
    to the first, and summing doubles an order at the moment somebody is least
    likely to re-read it.
    """
    incoming = _clean(items)
    stored = await db.scalar(select(Cart).where(Cart.user_id == user_id))
    merged = _clean(stored.items if stored else [])

    for product_id, quantity in incoming.items():
        merged[product_id] = max(merged.get(product_id, 0), quantity)

    if len(merged) > MAX_CART_ITEMS:
        # Keeping the newest is the least surprising truncation: they are the
        # ones the shopper was looking at a moment ago.
        merged = dict(list(merged.items())[-MAX_CART_ITEMS:])

    await _store(db, user_id, merged)
    return await _resolve(db, merged)


async def clear_cart(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Emptied rather than deleted, so the row's identity stays put."""
    await _store(db, user_id, {})
