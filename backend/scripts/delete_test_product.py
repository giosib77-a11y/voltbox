"""Delete one test product for good: its orders, its stock ledger, its files.

What it does: removes a product the admin panel will not delete because it
appears in an order. In one transaction it deletes every order that contains
the product (their order_items and order_status_history go with them, ON
DELETE CASCADE), then the product (its product_images and inventory_movements
cascade), and, with --with-category, its category once nothing else is in it.
After the commit it deletes the product's files from Storage. Each deletion is
written to admin_audit_log with no actor, as the panel would write it.
Where it fits: a one-off, run by hand from backend/ against whatever
DATABASE_URL points at - backend/.env names the live database. Run --dry-run
first: it opens a READ ONLY transaction, prints everything it would remove, and
removes nothing.

What it refuses, before touching anything:
  - a product whose name is not --expect-name, so a mistyped id stops here;
  - an order that also contains another product - deleting it would take a
    real sale of that product with it;
  - another product's inventory movement pointing at one of those orders -
    its ledger would lose the link to the sale that moved it;
  - a cart still holding the product;
  - with --with-category, a category that still has another product or a
    subcategory.
So every other product's stock and stock ledger are exactly as before.

Notes: the files go after the commit, not before, for the reason
admin_product.delete_product gives - a failed delete must not leave a product
pointing at files that no longer exist. A failure there leaves files under
products/<id>/ and nothing else; running again deletes them. The audit log is
kept: it is the record that this data existed and was removed.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

import httpx
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db.models import (
    Cart,
    Category,
    InventoryMovement,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductImage,
)
from app.db.session import SessionLocal, engine
from app.services import audit
from app.services.admin_image import _key_from_url
from app.services.storage import get_storage

ACTOR = "scripts/delete_test_product.py"


class RefusedError(Exception):
    """A condition under which nothing may be deleted."""


def _storage_keys_listed(product_id: uuid.UUID) -> list[str]:
    """Every object under products/<id>/ in the bucket. Listing changes nothing."""
    if not (
        settings.supabase_project_ref and settings.supabase_service_role_key.get_secret_value()
    ):
        return []
    key = settings.supabase_service_role_key.get_secret_value()
    prefix = f"products/{product_id}"
    response = httpx.post(
        f"https://{settings.supabase_project_ref}.supabase.co/storage/v1/object/list/"
        f"{settings.supabase_storage_bucket}",
        headers={"Authorization": f"Bearer {key}", "apikey": key},
        json={"prefix": prefix, "limit": 1000},
        timeout=30,
    )
    response.raise_for_status()
    return [f"{prefix}/{obj['name']}" for obj in response.json() if obj.get("id")]


async def plan(db: AsyncSession, product_id: uuid.UUID, expect_name: str, with_category: bool):
    """What would be removed, or RefusedError. Reads only."""
    product = await db.get(Product, product_id)
    if product is None:
        raise RefusedError(f"no product {product_id}")
    if product.name != expect_name:
        raise RefusedError(f"product {product_id} is named {product.name!r}, not {expect_name!r}")

    images = (
        await db.scalars(select(ProductImage).where(ProductImage.product_id == product_id))
    ).all()
    movements = (
        await db.scalars(
            select(InventoryMovement)
            .where(InventoryMovement.product_id == product_id)
            .order_by(InventoryMovement.created_at)
        )
    ).all()
    order_ids = list(
        (
            await db.scalars(select(OrderItem.order_id).where(OrderItem.product_id == product_id))
        ).unique()
    )
    orders = (
        (await db.scalars(select(Order).where(Order.id.in_(order_ids)))).all() if order_ids else []
    )

    for order in orders:
        others = await db.scalar(
            select(func.count())
            .select_from(OrderItem)
            .where(OrderItem.order_id == order.id, OrderItem.product_id != product_id)
        )
        if others:
            raise RefusedError(
                f"order {order.order_number} also contains {others} other product line(s)"
            )
    if order_ids:
        foreign = await db.scalar(
            select(func.count())
            .select_from(InventoryMovement)
            .where(
                InventoryMovement.order_id.in_(order_ids),
                InventoryMovement.product_id != product_id,
            )
        )
        if foreign:
            raise RefusedError(f"{foreign} movement(s) of other products point at these orders")

    carts = await db.scalar(
        select(func.count())
        .select_from(Cart)
        .where(text("items::text LIKE :pattern"))
        .params(pattern=f"%{product_id}%")
    )
    if carts:
        raise RefusedError(f"{carts} cart(s) still hold the product")

    items = (
        (await db.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_ids)))).all()
        if order_ids
        else []
    )
    history = (
        await db.scalar(
            select(func.count())
            .select_from(OrderStatusHistory)
            .where(OrderStatusHistory.order_id.in_(order_ids))
        )
        if order_ids
        else 0
    )

    category = await db.get(Category, product.category_id)
    category_note = "kept (run with --with-category to delete it)"
    if with_category:
        neighbours = await db.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.category_id == category.id, Product.id != product_id)
        )
        children = await db.scalar(
            select(func.count()).select_from(Category).where(Category.parent_id == category.id)
        )
        if neighbours or children:
            raise RefusedError(
                f"category {category.slug} still has {neighbours} other product(s)"
                f" and {children} subcategory(ies)"
            )
        category_note = "deleted - no other product and no subcategory"

    keys = set(_storage_keys_listed(product_id))
    keys |= {k for k in (_key_from_url(i.url) for i in images) if k}
    keys |= {k for k in (_key_from_url(i.image_url) for i in items if i.image_url) if k}

    return {
        "product": product,
        "images": images,
        "movements": movements,
        "orders": orders,
        "items": items,
        "history": history,
        "category": category,
        "category_note": category_note,
        "keys": sorted(keys),
    }


def report(p: dict) -> None:
    product, category = p["product"], p["category"]
    print(f"database : {engine.url.host}/{engine.url.database}")
    print(
        f"product  : {product.id}  {product.name!r}  slug={product.slug}"
        f"  sku={product.sku}  stock={product.stock}"
    )
    print(f"category : {category.id}  {category.name}  ({category.slug}) -> {p['category_note']}")
    print(f"\norders to delete ({len(p['orders'])}), with their items and status history:")
    for order in p["orders"]:
        print(
            f"  {order.id}  {order.order_number}  {order.status}"
            f"  total={order.total}  created={order.created_at:%Y-%m-%d}"
        )
    print(f"order_items to delete ({len(p['items'])}):")
    for item in p["items"]:
        print(f"  {item.id}  {item.product_name!r} x{item.quantity} @ {item.unit_price}")
    print(f"order_status_history rows to delete: {p['history']}")
    print(f"product_images to delete ({len(p['images'])}):")
    for image in p["images"]:
        print(f"  {image.id}  {image.url}")
    print(f"inventory_movements to delete ({len(p['movements'])}), this product's ledger only:")
    for m in p["movements"]:
        print(
            f"  {m.created_at:%Y-%m-%d %H:%M}  {m.reason:<18} {m.change:+d}"
            f"  {m.previous_stock} -> {m.new_stock}"
        )
    print(f"storage objects to delete after the commit ({len(p['keys'])}):")
    for key in p["keys"]:
        print(f"  {key}")
    print("audit log: kept; one row added per deleted order, the product and the category")


async def execute(db: AsyncSession, p: dict, with_category: bool) -> None:
    product, category = p["product"], p["category"]
    for order in p["orders"]:
        await audit.record(
            db,
            actor_id=None,
            action="order.delete",
            entity_type="order",
            entity_id=str(order.id),
            changes={"orderNumber": order.order_number, "total": order.total, "via": ACTOR},
        )
    if p["orders"]:
        await db.execute(delete(Order).where(Order.id.in_([o.id for o in p["orders"]])))
    await audit.record(
        db,
        actor_id=None,
        action="product.delete",
        entity_type="product",
        entity_id=str(product.id),
        changes={
            "slug": product.slug,
            "name": product.name,
            "sku": product.sku,
            "stock": product.stock,
            "via": ACTOR,
        },
    )
    await db.execute(delete(Product).where(Product.id == product.id))
    if with_category:
        await audit.record(
            db,
            actor_id=None,
            action="category.delete",
            entity_type="category",
            entity_id=str(category.id),
            changes={"slug": category.slug, "name": category.name, "via": ACTOR},
        )
        await db.execute(delete(Category).where(Category.id == category.id))


async def main(args: argparse.Namespace) -> int:
    product_id = uuid.UUID(args.product_id)
    async with SessionLocal() as db:
        if args.dry_run:
            # First statement of the transaction, so it governs all of it
            await db.execute(text("SET TRANSACTION READ ONLY"))
            assert (await db.scalar(text("SHOW transaction_read_only"))) == "on"
        try:
            p = await plan(db, product_id, args.expect_name, args.with_category)
        except RefusedError as reason:
            await db.rollback()
            print(f"REFUSED: {reason}. Nothing was changed.")
            return 1
        report(p)
        if args.dry_run:
            await db.rollback()
            print("\n--dry-run: read-only transaction rolled back. Nothing was changed.")
            return 0
        await execute(db, p, args.with_category)
        await db.commit()
        print("\ndatabase: committed")

    storage = get_storage()
    for key in p["keys"]:
        await storage.delete(key)
        print(f"storage : deleted {key}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--expect-name", required=True, help="the product's exact name, as a guard")
    parser.add_argument(
        "--with-category", action="store_true", help="also delete its category if empty"
    )
    parser.add_argument("--dry-run", action="store_true")
    sys.exit(asyncio.run(main(parser.parse_args())))
