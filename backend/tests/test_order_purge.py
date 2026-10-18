"""Permanent delete of a trashed order, and the 30-day purge.

What it covers (PROJECT.md -> Business Rules -> Order trash): `DELETE
/admin/orders/{id}` refuses a live order (409 `ORDER_NOT_IN_TRASH`) and removes
a trashed one with its items and status history, leaving the stock ledger rows
in place with `order_id` NULL; opening the order list purges every order trashed
more than 30 days ago and nothing younger; neither path touches stock; each
deletion leaves one `order.purge` audit row with no customer data in it; and a
purge racing a restore never deletes an order the restore got to first.

The refusal and the 31-day tests are the ones that fail on code without the
feature: before it the route did not exist (405) and an expired order stayed in
the trash for ever.

The two race tests use separate sessions, as tests/test_orders_concurrency.py
does, because a row lock only shows between independent connections; they
commit real rows and delete them again at the end.
"""

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.core.errors import NotFoundError
from app.db.models import (
    ROLE_ADMIN,
    AdminAuditLog,
    Brand,
    Category,
    InventoryMovement,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    User,
)
from app.db.session import SessionLocal
from app.services import order as order_service
from app.services import order_trash
from app.services.order_status import transition
from app.services.order_trash import TRASH_RETENTION
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

ADMIN = "/api/v1/admin"
MISSING = "00000000-0000-4000-8000-000000000000"

CUSTOMER = {
    "first_name": "გიორგი",
    "last_name": "ბერიძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
    "email": "giorgi@example.ge",
}


@pytest.fixture
async def admin(db: AsyncSession) -> User:
    return await make_user(db, email="purge-admin@voltbox.ge", role=ROLE_ADMIN)


@pytest.fixture
def headers(admin: User) -> dict[str, str]:
    return auth_header(admin)


async def _order(db: AsyncSession, *, slug: str, stock: int = 10, qty: int = 2) -> Order:
    category = await make_category(db, slug=f"cat-{slug}")
    brand = await make_brand(db, f"Brand-{slug}")
    product = await make_product(db, category, brand, slug=slug, stock=stock)
    return await order_service.create_order(
        db,
        items=[(product.id, qty)],
        customer=dict(CUSTOMER),
        payment_method="cash",
        user=None,
    )


async def _trashed(db: AsyncSession, order: Order, *, days_ago: float) -> None:
    """Put the order in the trash as of `days_ago`, writing `deleted_at` directly."""
    order.deleted_at = datetime.now(UTC) - timedelta(days=days_ago)
    await db.flush()


async def _exists(db: AsyncSession, order_id: object) -> bool:
    return bool(
        await db.scalar(select(func.count()).select_from(Order).where(Order.id == order_id))
    )


async def _items(db: AsyncSession, order_id: object) -> list[OrderItem]:
    return list((await db.scalars(select(OrderItem).where(OrderItem.order_id == order_id))).all())


async def _history(db: AsyncSession, order_id: object) -> list[OrderStatusHistory]:
    stmt = select(OrderStatusHistory).where(OrderStatusHistory.order_id == order_id)
    return list((await db.scalars(stmt)).all())


async def _purge_rows(db: AsyncSession, order_id: object) -> list[AdminAuditLog]:
    stmt = select(AdminAuditLog).where(
        AdminAuditLog.entity_id == str(order_id), AdminAuditLog.action == "order.purge"
    )
    return list((await db.scalars(stmt)).all())


async def _stock(db: AsyncSession, product_id: object) -> int | None:
    stock: int | None = await db.scalar(select(Product.stock).where(Product.id == product_id))
    return stock


async def _movements(db: AsyncSession, product_id: object) -> list[InventoryMovement]:
    stmt = select(InventoryMovement).where(InventoryMovement.product_id == product_id)
    return list((await db.scalars(stmt)).all())


async def _delete(
    client: httpx.AsyncClient, headers: dict[str, str], order_id: object
) -> httpx.Response:
    return await client.delete(f"{ADMIN}/orders/{order_id}", headers=headers)


# --- DELETE /admin/orders/{id} ------------------------------------------------


async def test_deleting_a_live_order_is_refused_and_the_order_is_intact(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="delete-live", qty=3)
    order_id, product_id = order.id, order.items[0].product_id
    await transition(db, order_id, "confirmed", actor_id=None)

    response = await _delete(client, headers, order_id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_NOT_IN_TRASH"
    assert await _exists(db, order_id)
    assert len(await _items(db, order_id)) == 1
    assert len(await _history(db, order_id)) == 2  # created, then confirmed
    assert await _stock(db, product_id) == 7
    assert await _purge_rows(db, order_id) == []


async def test_deleting_an_unknown_order_is_404(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    response = await _delete(client, headers, MISSING)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"


async def test_deleting_a_trashed_order_removes_it_and_keeps_the_stock_ledger(
    client: httpx.AsyncClient, headers: dict[str, str], admin: User, db: AsyncSession
) -> None:
    order = await _order(db, slug="delete-trashed", stock=10, qty=4)
    order_id, product_id = order.id, order.items[0].product_id
    number, total = order.order_number, order.total
    await transition(db, order_id, "confirmed", actor_id=None)
    await client.post(f"{ADMIN}/orders/{order_id}/trash", headers=headers)
    assert len(await _items(db, order_id)) == 1
    assert len(await _history(db, order_id)) == 2
    before = {m.id for m in await _movements(db, product_id)}
    assert before, "checkout wrote a ledger row for the order"
    assert await _stock(db, product_id) == 6

    response = await _delete(client, headers, order_id)

    assert response.status_code == 204
    assert response.content == b""
    assert not await _exists(db, order_id)
    assert await _items(db, order_id) == []
    assert await _history(db, order_id) == []
    # The ledger keeps its rows; only the link to the vanished order is cut.
    after = await _movements(db, product_id)
    assert {m.id for m in after} == before
    assert all(m.order_id is None for m in after)
    assert await _stock(db, product_id) == 6
    rows = await _purge_rows(db, order_id)
    assert len(rows) == 1
    assert rows[0].actor_id == admin.id
    assert rows[0].entity_type == "order"
    assert rows[0].changes == {
        "orderNumber": number,
        "status": "confirmed",
        "total": str(total),
        "automatic": False,
    }


async def test_deleting_twice_is_404_the_second_time(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="delete-twice")
    order_id = order.id
    await client.post(f"{ADMIN}/orders/{order_id}/trash", headers=headers)
    await _delete(client, headers, order_id)

    again = await _delete(client, headers, order_id)

    assert again.status_code == 404
    assert again.json()["error"]["code"] == "ORDER_NOT_FOUND"
    assert len(await _purge_rows(db, order_id)) == 1


async def test_the_purge_audit_row_holds_no_customer_data(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="delete-privacy")
    order_id = order.id
    await client.post(f"{ADMIN}/orders/{order_id}/trash", headers=headers)
    await _delete(client, headers, order_id)

    (row,) = await _purge_rows(db, order_id)

    assert set(row.changes) == {"orderNumber", "status", "total", "automatic"}
    assert isinstance(row.changes["total"], str)
    dumped = str(row.changes) + str(row.ip)
    for value in ("გიორგი", "ბერიძე", "555123456", "giorgi@example.ge", "ჭავჭავაძის"):
        assert value not in dumped


# --- the 30-day purge ---------------------------------------------------------


@pytest.mark.parametrize("params", [{}, {"trash": "true"}], ids=["live-list", "trash-list"])
async def test_opening_the_list_purges_an_order_trashed_31_days_ago(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    db: AsyncSession,
    params: dict[str, str],
) -> None:
    old = await _order(db, slug="purge-old", stock=10, qty=3)
    old_id, product_id = old.id, old.items[0].product_id
    number, total = old.order_number, old.total
    await transition(db, old_id, "confirmed", actor_id=None)
    await _trashed(db, old, days_ago=31)
    before = {m.id for m in await _movements(db, product_id)}
    assert await _stock(db, product_id) == 7

    response = await client.get(f"{ADMIN}/orders", headers=headers, params=params)

    assert response.status_code == 200
    assert not await _exists(db, old_id)
    assert await _items(db, old_id) == []
    assert await _history(db, old_id) == []
    assert await _stock(db, product_id) == 7
    after = await _movements(db, product_id)
    assert {m.id for m in after} == before
    assert all(m.order_id is None for m in after)
    (row,) = await _purge_rows(db, old_id)
    assert row.actor_id is None
    assert row.changes == {
        "orderNumber": number,
        "status": "confirmed",
        "total": str(total),
        "automatic": True,
    }
    assert response.json()["total"] == 0


async def test_the_purge_leaves_younger_trashed_orders_and_live_orders(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    live = await _order(db, slug="purge-live")
    young = await _order(db, slug="purge-young")
    edge = await _order(db, slug="purge-edge")
    old = await _order(db, slug="purge-gone")
    await _trashed(db, young, days_ago=29)
    # An hour inside the retention: not eligible yet, whichever way the boundary rounds.
    await _trashed(db, edge, days_ago=TRASH_RETENTION.days - 1 / 24)
    await _trashed(db, old, days_ago=31)
    ids = {"live": live.id, "young": young.id, "edge": edge.id, "old": old.id}

    live_list = await client.get(f"{ADMIN}/orders", headers=headers)
    trash_list = await client.get(f"{ADMIN}/orders", headers=headers, params={"trash": "true"})

    assert live_list.json()["total"] == 1
    assert {row["id"] for row in trash_list.json()["items"]} == {
        str(ids["young"]),
        str(ids["edge"]),
    }
    assert await _exists(db, ids["live"])
    assert await _exists(db, ids["young"])
    assert await _exists(db, ids["edge"])
    assert not await _exists(db, ids["old"])
    for kept in ("live", "young", "edge"):
        assert await _purge_rows(db, ids[kept]) == []
    assert len(await _purge_rows(db, ids["old"])) == 1


async def test_a_sweep_that_finds_nothing_writes_nothing(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="purge-nothing")
    await _trashed(db, order, days_ago=5)
    audit_before = await db.scalar(select(func.count()).select_from(AdminAuditLog))

    assert await order_trash.purge_expired(db) == 0
    await client.get(f"{ADMIN}/orders", headers=headers)

    assert await db.scalar(select(func.count()).select_from(AdminAuditLog)) == audit_before
    assert await _exists(db, order.id)


async def test_the_purge_takes_every_expired_order_in_one_call(db: AsyncSession) -> None:
    first = await _order(db, slug="purge-many-1")
    second = await _order(db, slug="purge-many-2")
    await _trashed(db, first, days_ago=40)
    await _trashed(db, second, days_ago=90)
    ids = (first.id, second.id)

    assert await order_trash.purge_expired(db) == 2

    for order_id in ids:
        assert not await _exists(db, order_id)
        (row,) = await _purge_rows(db, order_id)
        assert row.actor_id is None
        assert row.changes["automatic"] is True


# --- racing a restore ---------------------------------------------------------


@pytest.fixture
async def committed_order() -> AsyncGenerator[Order]:
    """An order trashed 31 days ago, committed on its own connection."""
    async with SessionLocal() as setup:
        category = Category(slug="purge-race", name="purge-race", filters=[])
        brand = Brand(slug="purge-race-brand", name="PurgeRaceBrand")
        setup.add_all([category, brand])
        await setup.flush()
        product = await make_product(setup, category, brand, slug="purge-race-product", stock=5)
        order = await order_service.create_order(
            setup,
            items=[(product.id, 2)],
            customer=dict(CUSTOMER),
            payment_method="cash",
            user=None,
        )
        order.deleted_at = datetime.now(UTC) - timedelta(days=31)
        await setup.commit()
        order_id, product_id = order.id, product.id

    async with SessionLocal() as session:
        loaded = await session.scalar(select(Order).where(Order.id == order_id))
        assert loaded is not None
        yield loaded

    async with SessionLocal() as cleanup:
        await cleanup.execute(delete(AdminAuditLog).where(AdminAuditLog.entity_type == "order"))
        await cleanup.execute(delete(Order).where(Order.id == order_id))
        await cleanup.execute(
            delete(InventoryMovement).where(InventoryMovement.product_id == product_id)
        )
        await cleanup.execute(delete(Product).where(Product.id == product_id))
        await cleanup.execute(delete(Category).where(Category.slug == "purge-race"))
        await cleanup.execute(delete(Brand).where(Brand.slug == "purge-race-brand"))
        await cleanup.commit()


async def _until_queued_behind(holder: AsyncSession) -> None:
    """Return once another connection waits on a lock `holder`'s transaction holds.

    Without it the test could commit the holder before the other side reached
    the row, and the race would not have happened.
    """
    pid = await holder.scalar(text("SELECT pg_backend_pid()"))
    async with SessionLocal() as probe:
        for _ in range(500):
            if await probe.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_locks"
                    " WHERE NOT granted AND :holder = ANY(pg_blocking_pids(pid)))"
                ),
                {"holder": pid},
            ):
                return
            await asyncio.sleep(0.01)
    raise AssertionError("nothing ever queued behind the held row")


async def _purge_in_own_session() -> int:
    async with SessionLocal() as session:
        purged = await order_trash.purge_expired(session)
        await session.commit()
        return purged


async def _restore_in_own_session(order_id: object) -> str:
    async with SessionLocal() as session:
        try:
            await order_trash.restore(session, order_id)  # type: ignore[arg-type]
            await session.commit()
        except NotFoundError as exc:
            await session.rollback()
            return exc.code
        return "restored"


async def test_a_restore_holding_the_row_wins_over_the_purge(committed_order: Order) -> None:
    """The restore has the row; the purge's DELETE waits, then finds it live.

    READ COMMITTED re-evaluates the WHERE on a row that changed while the
    statement waited, so an order restored in the same instant is not purged.
    """
    order_id = committed_order.id
    async with SessionLocal() as restoring:
        _, changed = await order_trash.restore(restoring, order_id)
        assert changed
        purging = asyncio.create_task(_purge_in_own_session())
        await _until_queued_behind(restoring)
        await restoring.commit()
    purged = await purging

    assert purged == 0
    async with SessionLocal() as check:
        stored = await check.scalar(select(Order).where(Order.id == order_id))
        assert stored is not None
        assert stored.deleted_at is None
        assert await _purge_rows(check, order_id) == []


async def test_a_purge_holding_the_row_makes_the_restore_a_404(committed_order: Order) -> None:
    order_id = committed_order.id
    async with SessionLocal() as purging:
        assert await order_trash.purge_expired(purging) == 1
        restoring = asyncio.create_task(_restore_in_own_session(order_id))
        await _until_queued_behind(purging)
        await purging.commit()
    answer = await restoring

    assert answer == "ORDER_NOT_FOUND"
    async with SessionLocal() as check:
        assert not await _exists(check, order_id)
        assert len(await _purge_rows(check, order_id)) == 1
        remaining = await check.scalar(
            select(func.count()).select_from(Order).where(Order.deleted_at.is_not(None))
        )
        assert remaining == 0


async def test_nothing_in_the_purge_path_writes_the_stock_ledger(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="ledger-untouched", stock=10, qty=2)
    product_id = order.items[0].product_id
    await _trashed(db, order, days_ago=31)
    spare = await _order(db, slug="ledger-spare", stock=10, qty=1)
    spare_id = spare.id
    await client.post(f"{ADMIN}/orders/{spare_id}/trash", headers=headers)
    movements = await db.scalar(select(func.count()).select_from(InventoryMovement))

    await client.get(f"{ADMIN}/orders", headers=headers)
    await _delete(client, headers, spare_id)

    assert await db.scalar(select(func.count()).select_from(InventoryMovement)) == movements
    assert await _stock(db, product_id) == 8
