"""The admin order trash: trash, restore, the frozen status and the trash list.

What it covers (PROJECT.md -> Business Rules -> Order trash): trashing sets
`deleted_at` and writes one audit row, repeating it changes nothing, restore
returns the order with the status it had, a trashed order refuses every status
change (409 `ORDER_IN_TRASH`) without touching stock or history, trash and
restore never write the stock ledger, and the live list, the trash list and the
dashboard counts each see only their own side.

The refusal tests are the ones that fail on code without the freeze: before it a
trashed order could still be cancelled, which restocks from a place the admin
does not look at.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.core.errors import ConflictError
from app.db.models import (
    ROLE_ADMIN,
    AdminAuditLog,
    InventoryMovement,
    Order,
    OrderStatusHistory,
    Product,
    User,
)
from app.services import order as order_service
from app.services.order_status import counts_by_status, transition
from app.services.order_trash import TRASH_RETENTION
from sqlalchemy import func, select
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
    return await make_user(db, email="trash-admin@voltbox.ge", role=ROLE_ADMIN)


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


async def _audit_rows(db: AsyncSession, order: Order, action: str) -> list[AdminAuditLog]:
    stmt = select(AdminAuditLog).where(
        AdminAuditLog.entity_id == str(order.id), AdminAuditLog.action == action
    )
    return list((await db.scalars(stmt)).all())


async def _count(
    db: AsyncSession, model: type[InventoryMovement] | type[OrderStatusHistory]
) -> int:
    return int(await db.scalar(select(func.count()).select_from(model)) or 0)


async def _trash(
    client: httpx.AsyncClient, headers: dict[str, str], order: Order
) -> httpx.Response:
    return await client.post(f"{ADMIN}/orders/{order.id}/trash", headers=headers)


async def _restore(
    client: httpx.AsyncClient, headers: dict[str, str], order: Order
) -> httpx.Response:
    return await client.post(f"{ADMIN}/orders/{order.id}/restore", headers=headers)


async def test_trashing_sets_deleted_at_purge_at_and_one_audit_row(
    client: httpx.AsyncClient, headers: dict[str, str], admin: User, db: AsyncSession
) -> None:
    order = await _order(db, slug="trash-basic")
    before = datetime.now(UTC)

    response = await _trash(client, headers, order)

    assert response.status_code == 200
    body = response.json()
    deleted_at = datetime.fromisoformat(body["deletedAt"])
    purge_at = datetime.fromisoformat(body["purgeAt"])
    assert before - timedelta(seconds=1) <= deleted_at <= datetime.now(UTC) + timedelta(seconds=1)
    assert purge_at - deleted_at == TRASH_RETENTION == timedelta(days=30)

    rows = await _audit_rows(db, order, "order.trash")
    assert len(rows) == 1
    assert rows[0].actor_id == admin.id
    assert rows[0].entity_type == "order"
    assert rows[0].changes["status"] == "pending"
    assert rows[0].changes["deletedAt"]


async def test_trashing_twice_keeps_the_first_deleted_at_and_one_audit_row(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="trash-twice")
    first = (await _trash(client, headers, order)).json()

    second_response = await _trash(client, headers, order)

    assert second_response.status_code == 200
    assert second_response.json()["deletedAt"] == first["deletedAt"]
    assert second_response.json()["purgeAt"] == first["purgeAt"]
    assert len(await _audit_rows(db, order, "order.trash")) == 1


async def test_restore_returns_the_status_it_had_and_writes_one_audit_row(
    client: httpx.AsyncClient, headers: dict[str, str], admin: User, db: AsyncSession
) -> None:
    order = await _order(db, slug="restore-basic")
    await transition(db, order.id, "confirmed", actor_id=None)
    await _trash(client, headers, order)

    response = await _restore(client, headers, order)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["deletedAt"] is None
    assert body["purgeAt"] is None
    # The status graph works again after the restore.
    assert body["allowedTransitions"] == ["processing", "cancelled"]

    rows = await _audit_rows(db, order, "order.restore")
    assert len(rows) == 1
    assert rows[0].actor_id == admin.id
    assert rows[0].changes == {"status": "confirmed", "deletedAt": None}


async def test_restoring_a_live_order_changes_nothing_and_writes_no_audit_row(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="restore-live")

    response = await _restore(client, headers, order)

    assert response.status_code == 200
    assert response.json()["deletedAt"] is None
    assert response.json()["status"] == "pending"
    assert await _audit_rows(db, order, "order.restore") == []


async def test_restore_then_trash_again_starts_a_new_retention_period(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="trash-again")
    await _trash(client, headers, order)
    # Age the first deletion, so a kept value would be visibly old.
    order.deleted_at = datetime.now(UTC) - timedelta(days=20)
    await db.flush()
    await _restore(client, headers, order)

    again = (await _trash(client, headers, order)).json()

    assert datetime.fromisoformat(again["deletedAt"]) > datetime.now(UTC) - timedelta(minutes=1)
    assert len(await _audit_rows(db, order, "order.trash")) == 2


@pytest.mark.parametrize("action", ["trash", "restore"])
async def test_an_unknown_order_is_404_order_not_found(
    client: httpx.AsyncClient, headers: dict[str, str], action: str
) -> None:
    response = await client.post(f"{ADMIN}/orders/{MISSING}/{action}", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"


async def test_a_status_change_on_a_trashed_order_is_refused_and_changes_nothing(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, stock=10, qty=3, slug="frozen")
    product_id = order.items[0].product_id
    await _trash(client, headers, order)
    stock = await db.scalar(select(Product.stock).where(Product.id == product_id))
    movements = await _count(db, InventoryMovement)
    history = await _count(db, OrderStatusHistory)

    response = await client.post(
        f"{ADMIN}/orders/{order.id}/status", headers=headers, json={"to": "cancelled"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_IN_TRASH"
    await db.refresh(order)
    assert order.status == "pending"
    assert await db.scalar(select(Product.stock).where(Product.id == product_id)) == stock == 7
    assert await _count(db, InventoryMovement) == movements
    assert await _count(db, OrderStatusHistory) == history
    assert await _audit_rows(db, order, "order.status") == []


async def test_a_trashed_order_reports_in_trash_even_for_a_move_the_graph_forbids(
    db: AsyncSession,
) -> None:
    """The check sits before INVALID_TRANSITION: pending -> delivered is not in
    the graph either, but the useful answer is "restore it first"."""
    order = await _order(db, slug="frozen-order-of-checks")
    order.deleted_at = datetime.now(UTC)
    await db.flush()

    with pytest.raises(ConflictError) as caught:
        await transition(db, order.id, "delivered", actor_id=None)

    assert caught.value.code == "ORDER_IN_TRASH"


async def test_trashing_and_restoring_leave_stock_and_the_ledger_alone(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, stock=10, qty=4, slug="stock-untouched")
    product_id = order.items[0].product_id
    movements = await _count(db, InventoryMovement)
    history = await _count(db, OrderStatusHistory)
    assert await db.scalar(select(Product.stock).where(Product.id == product_id)) == 6

    await _trash(client, headers, order)
    assert await db.scalar(select(Product.stock).where(Product.id == product_id)) == 6
    assert await _count(db, InventoryMovement) == movements

    await _restore(client, headers, order)
    assert await db.scalar(select(Product.stock).where(Product.id == product_id)) == 6
    assert await _count(db, InventoryMovement) == movements
    # Neither is a status change, so the timeline has no entry for them.
    assert await _count(db, OrderStatusHistory) == history


async def test_the_detail_of_a_trashed_order_opens_with_no_allowed_moves(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="trashed-detail")
    await _trash(client, headers, order)

    response = await client.get(f"{ADMIN}/orders/{order.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["allowedTransitions"] == []
    assert body["deletedAt"] is not None
    assert body["status"] == "pending"


async def test_the_default_list_hides_a_trashed_order(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    live = await _order(db, slug="list-live")
    gone = await _order(db, slug="list-gone")
    await _trash(client, headers, gone)

    body = (await client.get(f"{ADMIN}/orders", headers=headers)).json()

    assert body["total"] == 1
    assert [row["orderNumber"] for row in body["items"]] == [live.order_number]
    assert body["items"][0]["deletedAt"] is None
    assert body["items"][0]["purgeAt"] is None
    # Searching for it by its number finds nothing either.
    searched = await client.get(f"{ADMIN}/orders", headers=headers, params={"q": gone.order_number})
    assert searched.json()["total"] == 0


async def test_the_trash_list_has_only_trashed_orders_newest_deletion_first(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    await _order(db, slug="trash-list-live")
    older = await _order(db, slug="trash-list-older")
    newer = await _order(db, slug="trash-list-newer")
    await _trash(client, headers, older)
    await _trash(client, headers, newer)
    # Explicit instants: two requests in one test can land on the same clock tick.
    older.deleted_at = datetime.now(UTC) - timedelta(days=3)
    newer.deleted_at = datetime.now(UTC) - timedelta(days=1)
    await db.flush()

    body = (await client.get(f"{ADMIN}/orders", headers=headers, params={"trash": "true"})).json()

    assert body["total"] == 2
    assert [row["orderNumber"] for row in body["items"]] == [
        newer.order_number,
        older.order_number,
    ]
    first = body["items"][0]
    assert datetime.fromisoformat(first["purgeAt"]) - datetime.fromisoformat(
        first["deletedAt"]
    ) == timedelta(days=30)


async def test_the_trash_list_still_applies_q_and_status(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    pending = await _order(db, slug="trash-filter-pending")
    confirmed = await _order(db, slug="trash-filter-confirmed")
    await transition(db, confirmed.id, "confirmed", actor_id=None)
    await _trash(client, headers, pending)
    await _trash(client, headers, confirmed)
    params = {"trash": "true"}

    by_status = await client.get(
        f"{ADMIN}/orders", headers=headers, params={**params, "status": "confirmed"}
    )
    by_number = await client.get(
        f"{ADMIN}/orders", headers=headers, params={**params, "q": pending.order_number}
    )

    assert [row["orderNumber"] for row in by_status.json()["items"]] == [confirmed.order_number]
    assert [row["orderNumber"] for row in by_number.json()["items"]] == [pending.order_number]


async def test_a_bad_trash_flag_is_a_validation_error(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.get(f"{ADMIN}/orders", headers=headers, params={"trash": "maybe"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_counts_by_status_excludes_the_trash(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    await _order(db, slug="count-live")
    gone = await _order(db, slug="count-gone")
    await _trash(client, headers, gone)

    counts = await counts_by_status(db)
    dashboard = (await client.get(f"{ADMIN}/dashboard", headers=headers)).json()

    assert counts["pending"] == 1
    assert dashboard["ordersByStatus"]["pending"] == 1

    await _restore(client, headers, gone)
    assert (await counts_by_status(db))["pending"] == 2
