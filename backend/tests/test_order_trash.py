"""The admin order trash: trash, restore, the frozen status and the trash list.

What it covers (PROJECT.md -> Business Rules -> Order trash): only an order in a
final status (cancelled, delivered) can be trashed - an active one is 409
`ORDER_STILL_ACTIVE`, because its stock comes back only on a cancellation and
trash/purge would lose it (A-116); trashing sets `deleted_at` and writes one
audit row, repeating it changes nothing, restore returns the order with the
status it had, a trashed order refuses every status change (409
`ORDER_IN_TRASH`) without touching stock or history, trash and restore never
write the stock ledger, and the live list, the trash list and the dashboard
counts each see only their own side.

The refusal tests are the ones that fail on code without the freeze: before it a
trashed order could still be cancelled, which restocks from a place the admin
does not look at. The ORDER_STILL_ACTIVE tests fail on code without the status
rule. A trashed active order can no longer be made through the route, so tests
about one (the freeze, restore) write `deleted_at` directly, which is also how a
row trashed before the rule looks.
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
from app.services.order_status import (
    FINAL_STATUSES,
    TRANSITIONS,
    counts_by_status,
    is_final,
    transition,
)
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


async def _cancelled(db: AsyncSession, *, slug: str, stock: int = 10, qty: int = 2) -> Order:
    """An order in a final status: cancelled, so its stock is already back."""
    order = await _order(db, slug=slug, stock=stock, qty=qty)
    await transition(db, order.id, "cancelled", actor_id=None)
    return order


async def _delivered(db: AsyncSession, *, slug: str, stock: int = 10, qty: int = 2) -> Order:
    order = await _order(db, slug=slug, stock=stock, qty=qty)
    for step in ("confirmed", "processing", "shipped", "delivered"):
        await transition(db, order.id, step, actor_id=None)
    return order


async def _legacy_trashed(db: AsyncSession, order: Order) -> None:
    """An active order in the trash - what the route can no longer produce."""
    order.deleted_at = datetime.now(UTC)
    await db.flush()


async def _stock(db: AsyncSession, product_id: object) -> int | None:
    stock: int | None = await db.scalar(select(Product.stock).where(Product.id == product_id))
    return stock


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
    order = await _cancelled(db, slug="trash-basic")
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
    assert rows[0].changes["status"] == "cancelled"
    assert rows[0].changes["deletedAt"]


async def test_trashing_twice_keeps_the_first_deleted_at_and_one_audit_row(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _cancelled(db, slug="trash-twice")
    first = (await _trash(client, headers, order)).json()

    second_response = await _trash(client, headers, order)

    assert second_response.status_code == 200
    assert second_response.json()["deletedAt"] == first["deletedAt"]
    assert second_response.json()["purgeAt"] == first["purgeAt"]
    assert len(await _audit_rows(db, order, "order.trash")) == 1


async def test_restore_returns_the_status_it_had_and_writes_one_audit_row(
    client: httpx.AsyncClient, headers: dict[str, str], admin: User, db: AsyncSession
) -> None:
    # A confirmed order in the trash is the state of a row trashed before the
    # status rule: the route no longer produces it, restore still has to cope.
    order = await _order(db, slug="restore-basic")
    await transition(db, order.id, "confirmed", actor_id=None)
    await _legacy_trashed(db, order)

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


async def test_a_trashed_final_order_restores_with_its_status(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _delivered(db, slug="restore-delivered")
    await _trash(client, headers, order)

    body = (await _restore(client, headers, order)).json()

    assert body["status"] == "delivered"
    assert body["deletedAt"] is None
    assert body["allowedTransitions"] == []


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
    order = await _cancelled(db, slug="trash-again")
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
    await _legacy_trashed(db, order)
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
    order = await _cancelled(db, stock=10, qty=4, slug="stock-untouched")
    product_id = order.items[0].product_id
    movements = await _count(db, InventoryMovement)
    history = await _count(db, OrderStatusHistory)
    # The cancellation already returned the four units.
    assert await _stock(db, product_id) == 10

    await _trash(client, headers, order)
    assert await _stock(db, product_id) == 10
    assert await _count(db, InventoryMovement) == movements

    await _restore(client, headers, order)
    assert await _stock(db, product_id) == 10
    assert await _count(db, InventoryMovement) == movements
    # Neither is a status change, so the timeline has no entry for them.
    assert await _count(db, OrderStatusHistory) == history


async def test_the_detail_of_a_trashed_order_opens_with_no_allowed_moves(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    # A legacy active order: the one whose moves would be non-empty without the freeze.
    order = await _order(db, slug="trashed-detail")
    await _legacy_trashed(db, order)

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
    gone = await _cancelled(db, slug="list-gone")
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
    older = await _cancelled(db, slug="trash-list-older")
    newer = await _cancelled(db, slug="trash-list-newer")
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
    cancelled = await _cancelled(db, slug="trash-filter-cancelled")
    delivered = await _delivered(db, slug="trash-filter-delivered")
    await _trash(client, headers, cancelled)
    await _trash(client, headers, delivered)
    params = {"trash": "true"}

    by_status = await client.get(
        f"{ADMIN}/orders", headers=headers, params={**params, "status": "delivered"}
    )
    by_number = await client.get(
        f"{ADMIN}/orders", headers=headers, params={**params, "q": cancelled.order_number}
    )

    assert [row["orderNumber"] for row in by_status.json()["items"]] == [delivered.order_number]
    assert [row["orderNumber"] for row in by_number.json()["items"]] == [cancelled.order_number]


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
    gone = await _cancelled(db, slug="count-gone")
    await _trash(client, headers, gone)

    counts = await counts_by_status(db)
    dashboard = (await client.get(f"{ADMIN}/dashboard", headers=headers)).json()

    assert counts["pending"] == 1
    assert counts["cancelled"] == 0
    assert dashboard["ordersByStatus"]["cancelled"] == 0

    await _restore(client, headers, gone)
    assert (await counts_by_status(db))["cancelled"] == 1


# --- only a final order may be trashed (A-116) --------------------------------

#: The way from `pending` to each active status.
ACTIVE_PATHS = {
    "pending": (),
    "confirmed": ("confirmed",),
    "processing": ("confirmed", "processing"),
    "shipped": ("confirmed", "processing", "shipped"),
}


def test_the_final_statuses_are_the_ones_the_graph_leaves_nowhere_from() -> None:
    dead_ends = {status for status, following in TRANSITIONS.items() if not following}
    assert set(FINAL_STATUSES) == dead_ends
    assert sorted(FINAL_STATUSES) == ["cancelled", "delivered"]
    assert all(is_final(s) for s in FINAL_STATUSES)
    # `shipped` still has a move; an unknown status is not final.
    assert not is_final("shipped")
    assert not is_final("no-such-status")


@pytest.mark.parametrize("status", list(ACTIVE_PATHS))
async def test_trashing_an_active_order_is_refused_and_changes_nothing(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession, status: str
) -> None:
    order = await _order(db, slug=f"active-{status}", qty=3)
    for step in ACTIVE_PATHS[status]:
        await transition(db, order.id, step, actor_id=None)
    product_id = order.items[0].product_id
    assert order.status == status
    stock = await _stock(db, product_id)
    movements = await _count(db, InventoryMovement)
    history = await _count(db, OrderStatusHistory)

    response = await _trash(client, headers, order)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "ORDER_STILL_ACTIVE"
    assert error["details"] == {"status": status}
    await db.refresh(order)
    assert order.deleted_at is None
    assert order.status == status
    assert await _stock(db, product_id) == stock == 7
    assert await _count(db, InventoryMovement) == movements
    assert await _count(db, OrderStatusHistory) == history
    assert await _audit_rows(db, order, "order.trash") == []


@pytest.mark.parametrize("status", ["cancelled", "delivered"])
async def test_a_final_order_can_be_trashed(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession, status: str
) -> None:
    make = _cancelled if status == "cancelled" else _delivered
    order = await make(db, slug=f"final-{status}")
    product_id = order.items[0].product_id
    stock = await _stock(db, product_id)
    movements = await _count(db, InventoryMovement)

    response = await _trash(client, headers, order)

    assert response.status_code == 200
    assert response.json()["deletedAt"] is not None
    assert response.json()["status"] == status
    assert len(await _audit_rows(db, order, "order.trash")) == 1
    # Trashing writes no stock: the cancellation already returned it, a
    # delivered order's stock has left the shop.
    assert await _stock(db, product_id) == stock
    assert await _count(db, InventoryMovement) == movements


async def test_cancelling_first_makes_an_active_order_trashable_and_returns_its_stock(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="cancel-then-trash", qty=4)
    product_id = order.items[0].product_id
    refused = await _trash(client, headers, order)
    assert refused.json()["error"]["code"] == "ORDER_STILL_ACTIVE"
    assert await _stock(db, product_id) == 6

    cancelled = await client.post(
        f"{ADMIN}/orders/{order.id}/status", headers=headers, json={"to": "cancelled"}
    )
    trashed = await _trash(client, headers, order)

    assert cancelled.status_code == 200
    assert trashed.status_code == 200
    assert await _stock(db, product_id) == 10


async def test_trashing_an_already_trashed_active_order_is_still_a_no_op(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    """Repeating trash stays a retry-safe no-op even for a legacy active order:
    the status rule is for a fresh trash, not a 409 on a double click."""
    order = await _order(db, slug="trash-retry-legacy")
    await _legacy_trashed(db, order)

    response = await _trash(client, headers, order)

    assert response.status_code == 200
    assert await _audit_rows(db, order, "order.trash") == []


async def test_a_legacy_trashed_active_order_restores_and_cancelling_returns_its_stock(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="legacy-restore-cancel", qty=3)
    await transition(db, order.id, "confirmed", actor_id=None)
    order_id, product_id = order.id, order.items[0].product_id
    await _legacy_trashed(db, order)
    assert await _stock(db, product_id) == 7

    restored = await _restore(client, headers, order)
    cancelled = await client.post(
        f"{ADMIN}/orders/{order_id}/status", headers=headers, json={"to": "cancelled"}
    )

    assert restored.status_code == 200
    assert cancelled.status_code == 200
    assert await _stock(db, product_id) == 10
    returned = list(
        (
            await db.scalars(
                select(InventoryMovement).where(
                    InventoryMovement.product_id == product_id,
                    InventoryMovement.reason == "order_cancelled",
                )
            )
        ).all()
    )
    assert len(returned) == 1
    assert returned[0].change == 3
    assert returned[0].order_id == order_id
    # Now that its stock is back it may go to the trash.
    assert (await _trash(client, headers, order)).status_code == 200
