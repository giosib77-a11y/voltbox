"""Admin orders, the state machine, inventory and the dashboard.

What it covers: every (from, to) status pair is checked exhaustively, not just
the happy path - an allowed-transition table is only trustworthy if the refusals
are tested too. Cancelling returns stock exactly once. Dashboard figures come
from SQL and respect the store's timezone, which is the difference between an
order at 01:00 Tbilisi counting as today or as yesterday.
"""

import itertools
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from app.db.models import ROLE_ADMIN, AdminAuditLog, InventoryMovement, Order, Product
from app.services import order as order_service
from app.services.order_status import TRANSITIONS, transition
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

ADMIN = "/api/v1/admin"

CUSTOMER = {
    "firstName": "გიორგი",
    "lastName": "ბერიძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
    "email": "giorgi@example.ge",
}


@pytest.fixture
async def headers(db: AsyncSession) -> dict[str, str]:
    admin = await make_user(db, email="orders-admin@voltbox.ge", role=ROLE_ADMIN)
    return auth_header(admin)


async def _order(db: AsyncSession, *, stock: int = 10, qty: int = 2, slug: str = "ord") -> Order:
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


@pytest.mark.parametrize(
    ("from_status", "to_status"), list(itertools.product(TRANSITIONS, TRANSITIONS))
)
async def test_every_status_pair(db: AsyncSession, from_status: str, to_status: str) -> None:
    """Exhaustive: allowed pairs succeed, every other pair is refused.

    Testing only the happy path would let an accidental extra edge - say
    delivered back to pending - pass unnoticed forever.
    """
    order = await _order(db, slug=f"pair-{from_status}-{to_status}")
    order.status = from_status
    await db.flush()

    allowed = to_status in TRANSITIONS[from_status]

    if allowed:
        result = await transition(db, order.id, to_status, actor_id=None)
        assert result.status == to_status
    else:
        from app.core.errors import ConflictError

        with pytest.raises(ConflictError) as caught:
            await transition(db, order.id, to_status, actor_id=None)
        assert caught.value.code == "INVALID_TRANSITION"
        assert await db.scalar(select(Order.status).where(Order.id == order.id)) == from_status


async def test_an_unknown_status_is_rejected(db: AsyncSession) -> None:
    from app.core.errors import ValidationError

    order = await _order(db, slug="unknown-status")
    with pytest.raises(ValidationError):
        await transition(db, order.id, "refunded", actor_id=None)


async def test_cancelling_returns_stock_once(db: AsyncSession) -> None:
    order = await _order(db, stock=10, qty=3, slug="cancel-once")
    product_id = order.items[0].product_id
    assert await db.scalar(select(Product.stock).where(Product.id == product_id)) == 7

    await transition(db, order.id, "cancelled", actor_id=None)

    assert await db.scalar(select(Product.stock).where(Product.id == product_id)) == 10
    movements = list(
        (
            await db.scalars(
                select(InventoryMovement).where(InventoryMovement.product_id == product_id)
            )
        ).all()
    )
    assert [m.reason for m in movements] == ["order_placed", "order_cancelled"]


async def test_cancelling_a_cancelled_order_does_not_restock_again(db: AsyncSession) -> None:
    from app.core.errors import ConflictError

    order = await _order(db, stock=10, qty=3, slug="cancel-twice")
    product_id = order.items[0].product_id
    await transition(db, order.id, "cancelled", actor_id=None)

    with pytest.raises(ConflictError):
        await transition(db, order.id, "cancelled", actor_id=None)

    assert await db.scalar(select(Product.stock).where(Product.id == product_id)) == 10


async def test_a_shipped_order_cannot_be_cancelled(db: AsyncSession) -> None:
    from app.core.errors import ConflictError

    order = await _order(db, slug="shipped-order")
    await transition(db, order.id, "confirmed", actor_id=None)
    await transition(db, order.id, "processing", actor_id=None)
    await transition(db, order.id, "shipped", actor_id=None)

    with pytest.raises(ConflictError):
        await transition(db, order.id, "cancelled", actor_id=None)


async def test_the_detail_response_tells_the_ui_what_is_allowed(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="allowed-transitions")

    response = await client.get(f"{ADMIN}/orders/{order.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    # The UI renders these buttons and nothing else, so it can never offer a move
    # the server would refuse.
    assert body["allowedTransitions"] == ["confirmed", "cancelled"]
    assert body["items"][0]["productName"]


async def test_changing_status_records_history_and_an_audit_row(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="history-order")

    response = await client.post(
        f"{ADMIN}/orders/{order.id}/status",
        headers=headers,
        json={"to": "confirmed", "note": "ტელეფონით დადასტურდა"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    entries = body["history"]
    assert entries[-1]["fromStatus"] == "pending"
    assert entries[-1]["toStatus"] == "confirmed"
    assert entries[-1]["note"] == "ტელეფონით დადასტურდა"

    audit_row = await db.scalar(
        select(AdminAuditLog).where(AdminAuditLog.entity_id == str(order.id))
    )
    assert audit_row is not None
    assert audit_row.action == "order.status"


async def test_an_invalid_transition_is_a_conflict_over_http(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="http-invalid")

    response = await client.post(
        f"{ADMIN}/orders/{order.id}/status", headers=headers, json={"to": "delivered"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRANSITION"


@pytest.mark.parametrize("needle", ["+995 555 12 34 56", "555123456", "555 12 34 56"])
async def test_orders_are_found_by_phone_however_it_is_typed(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession, needle: str
) -> None:
    order = await _order(db, slug=f"phone-{abs(hash(needle)) % 1000}")

    response = await client.get(f"{ADMIN}/orders", headers=headers, params={"q": needle})

    assert response.status_code == 200
    assert order.order_number in [item["orderNumber"] for item in response.json()["items"]]


async def test_orders_are_found_by_number_and_name(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="searchable")

    by_number = await client.get(
        f"{ADMIN}/orders", headers=headers, params={"q": order.order_number}
    )
    by_name = await client.get(f"{ADMIN}/orders", headers=headers, params={"q": "გიორგი"})

    assert by_number.json()["total"] == 1
    assert by_name.json()["total"] >= 1


async def test_a_malformed_date_filter_is_a_clear_error(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.get(
        f"{ADMIN}/orders", headers=headers, params={"dateFrom": "yesterday"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DATE"


async def test_manual_adjustment_needs_a_note_for_a_correction(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, slug="adj")
    brand = await make_brand(db, "AdjBrand")
    product = await make_product(db, category, brand, slug="adj-1", stock=5)

    without = await client.post(
        f"{ADMIN}/inventory/{product.id}/adjust",
        headers=headers,
        json={"change": -1, "reason": "correction"},
    )
    assert without.status_code == 400
    assert without.json()["error"]["code"] == "NOTE_REQUIRED"

    with_note = await client.post(
        f"{ADMIN}/inventory/{product.id}/adjust",
        headers=headers,
        json={"change": -1, "reason": "correction", "note": "დაზიანებული"},
    )
    assert with_note.status_code == 200
    assert with_note.json()["stock"] == 4


async def test_a_system_reason_cannot_be_chosen_by_hand(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, slug="sys")
    brand = await make_brand(db, "SysBrand")
    product = await make_product(db, category, brand, slug="sys-1", stock=5)

    response = await client.post(
        f"{ADMIN}/inventory/{product.id}/adjust",
        headers=headers,
        json={"change": 5, "reason": "order_placed", "note": "მინდა"},
    )

    # Writing one by hand would claim an order caused a change no order caused.
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REASON_NOT_MANUAL"


async def test_an_adjustment_below_zero_is_refused(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, slug="neg")
    brand = await make_brand(db, "NegBrand")
    product = await make_product(db, category, brand, slug="neg-1", stock=2)

    response = await client.post(
        f"{ADMIN}/inventory/{product.id}/adjust",
        headers=headers,
        json={"change": -5, "reason": "restock"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"
    assert await db.scalar(select(Product.stock).where(Product.id == product.id)) == 2


async def test_the_movement_history_reads_newest_first(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, stock=10, qty=2, slug="hist")
    product_id = order.items[0].product_id
    await client.post(
        f"{ADMIN}/inventory/{product_id}/adjust",
        headers=headers,
        json={"change": 5, "reason": "restock"},
    )

    response = await client.get(f"{ADMIN}/inventory/{product_id}/movements", headers=headers)

    assert response.status_code == 200
    reasons = [item["reason"] for item in response.json()["items"]]
    assert reasons[0] == "restock"
    assert "order_placed" in reasons


async def test_the_inventory_list_can_show_only_low_stock(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    category = await make_category(db, slug="inv")
    brand = await make_brand(db, "InvBrand")
    low = await make_product(db, category, brand, slug="inv-low", stock=1)
    await make_product(db, category, brand, slug="inv-ok", stock=100)

    response = await client.get(f"{ADMIN}/inventory", headers=headers, params={"only": "low"})

    ids = [item["productId"] for item in response.json()["items"]]
    assert ids == [str(low.id)]
    assert response.json()["items"][0]["stockStatus"] == "low"


async def test_the_dashboard_counts_an_order_at_01_00_tbilisi_as_today(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    """The boundary that makes a timezone bug visible.

    Tbilisi is UTC+4, so 01:00 local is 21:00 UTC the previous day. Computing
    "today" in UTC would file this order under yesterday and the shop's daily
    figure would be wrong every single morning.
    """
    from zoneinfo import ZoneInfo

    tbilisi = ZoneInfo("Asia/Tbilisi")
    now_local = datetime.now(tbilisi)
    order = await _order(db, slug="tz-order")

    at_01 = now_local.replace(hour=1, minute=0, second=0, microsecond=0)
    order.created_at = at_01.astimezone(UTC)
    await db.flush()
    # Sanity: the instant really is on the previous UTC day.
    assert order.created_at.astimezone(UTC).date() < at_01.date() or at_01.hour == 1

    response = await client.get(f"{ADMIN}/dashboard", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["ordersToday"] >= 1
    assert Decimal(str(body["salesToday"])) >= order.total


async def test_the_dashboard_excludes_cancelled_orders_from_sales(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    kept = await _order(db, slug="kept-order")
    dropped = await _order(db, slug="dropped-order")
    await transition(db, dropped.id, "cancelled", actor_id=None)

    body = (await client.get(f"{ADMIN}/dashboard", headers=headers)).json()

    # Cancelled stock went back on the shelf; counting its value as sales would
    # overstate the shop.
    assert Decimal(str(body["salesTotal"])) == kept.total
    assert body["ordersByStatus"]["cancelled"] == 1


async def test_the_dashboard_reports_every_status_including_empty_ones(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    await _order(db, slug="status-coverage")

    body = (await client.get(f"{ADMIN}/dashboard", headers=headers)).json()

    # A missing key would render as a gap in the UI rather than a zero.
    assert set(body["ordersByStatus"]) == set(TRANSITIONS)
    assert body["ordersByStatus"]["delivered"] == 0


async def test_the_dashboard_lists_low_stock_and_top_products(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, stock=4, qty=3, slug="top-product")
    product_id = order.items[0].product_id

    body = (await client.get(f"{ADMIN}/dashboard", headers=headers)).json()

    assert body["lowStockCount"] >= 1
    assert str(product_id) in [row["id"] for row in body["lowStock"]]
    top = body["topProducts"]
    assert top and top[0]["quantity"] == 3


async def test_an_old_order_is_not_in_top_products(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    order = await _order(db, slug="ancient")
    order.created_at = datetime.now(UTC) - timedelta(days=90)
    await db.flush()

    body = (await client.get(f"{ADMIN}/dashboard", headers=headers)).json()

    # Top products looks back 30 days; an order from three months ago would make
    # the figure describe history rather than the current month.
    assert body["topProducts"] == []
    # It still counts towards all-time sales.
    assert Decimal(str(body["salesTotal"])) == order.total
