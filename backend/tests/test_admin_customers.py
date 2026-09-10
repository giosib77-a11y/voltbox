"""Admin customers.

What it covers: the aggregates match the rules used elsewhere (cancelled orders
do not count as spend), blocking revokes sessions rather than merely flipping a
flag, and no response ever carries a credential.

The last one is the reason explicit response models exist at all, so it is
asserted rather than assumed.
"""

from decimal import Decimal

import httpx
import pytest
from app.db.models import ROLE_ADMIN, RefreshToken, User
from app.services import auth as auth_service
from app.services import order as order_service
from app.services.order_status import transition
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

ADMIN = "/api/v1/admin"


@pytest.fixture
async def admin(db: AsyncSession) -> User:
    return await make_user(db, email="customers-admin@voltbox.ge", role=ROLE_ADMIN)


@pytest.fixture
def headers(admin: User) -> dict[str, str]:
    return auth_header(admin)


async def _customer_with_orders(db: AsyncSession) -> tuple[User, object, object]:
    customer = await make_user(db, email="shopper@example.ge")
    category = await make_category(db, slug="cust")
    brand = await make_brand(db, "CustBrand")
    product = await make_product(db, category, brand, slug="cust-1", price="100.00", stock=50)

    kept = await order_service.create_order(
        db,
        items=[(product.id, 2)],
        customer={"firstName": "შემსყიდველი", "phone": "555111222"},
        payment_method="cash",
        user=customer,
    )
    dropped = await order_service.create_order(
        db,
        items=[(product.id, 1)],
        customer={"firstName": "შემსყიდველი", "phone": "555111222"},
        payment_method="cash",
        user=customer,
    )
    await transition(db, dropped.id, "cancelled", actor_id=None)
    return customer, kept, dropped


async def test_the_list_reports_orders_and_spend_excluding_cancelled(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    customer, kept, _ = await _customer_with_orders(db)

    response = await client.get(f"{ADMIN}/customers", headers=headers, params={"q": "shopper"})

    assert response.status_code == 200
    (row,) = response.json()["items"]
    assert row["ordersCount"] == 2
    # Cancelled goods went back on the shelf, so they are not spend - the same
    # rule the dashboard uses.
    #
    # Money arrives as a JSON string: Pydantic serialises Decimal that way, and
    # it is the right choice here - a float would round 10.10 to 10.099999...
    # Both consumers (the storefront's formatNumber and the admin's money())
    # accept either form.
    assert Decimal(row["totalSpent"]) == kept.total
    assert row["id"] == str(customer.id)


async def test_the_detail_shows_addresses_and_order_history(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    customer, kept, dropped = await _customer_with_orders(db)

    response = await client.get(f"{ADMIN}/customers/{customer.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    numbers = [order["orderNumber"] for order in body["orders"]]
    assert kept.order_number in numbers
    assert dropped.order_number in numbers
    assert body["addresses"] == []


async def test_a_customer_response_never_carries_a_credential(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    customer = await make_user(db, email="secret@example.ge")

    detail = (await client.get(f"{ADMIN}/customers/{customer.id}", headers=headers)).json()
    listed = (await client.get(f"{ADMIN}/customers", headers=headers)).json()

    serialized = f"{detail}{listed}"
    for forbidden in ("passwordHash", "password_hash", "tokenHash", "token_hash", "$argon2"):
        assert forbidden not in serialized


async def test_blocking_revokes_every_refresh_token(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    customer = await make_user(db, email="blockme@example.ge")
    await auth_service._issue_session(db, customer)
    await auth_service._issue_session(db, customer)

    live = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == customer.id, RefreshToken.revoked_at.is_(None)
        )
    )
    assert len(list(live)) == 2

    response = await client.post(
        f"{ADMIN}/customers/{customer.id}/active", headers=headers, json={"isActive": False}
    )

    assert response.status_code == 200
    assert response.json()["isActive"] is False
    # Flipping the flag alone would leave a live refresh token minting new
    # access tokens for up to 30 days.
    still_live = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == customer.id, RefreshToken.revoked_at.is_(None)
        )
    )
    assert list(still_live) == []


async def test_a_blocked_customer_cannot_use_the_api(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    customer = await make_user(db, email="denied@example.ge")
    customer_headers = auth_header(customer)
    assert (await client.get("/api/v1/auth/me", headers=customer_headers)).status_code == 200

    await client.post(
        f"{ADMIN}/customers/{customer.id}/active", headers=headers, json={"isActive": False}
    )

    # get_current_user re-reads the row, so the existing access token dies at
    # once rather than when it expires.
    assert (await client.get("/api/v1/auth/me", headers=customer_headers)).status_code == 401


async def test_unblocking_restores_access(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    customer = await make_user(db, email="restore@example.ge", is_active=False)

    response = await client.post(
        f"{ADMIN}/customers/{customer.id}/active", headers=headers, json={"isActive": True}
    )

    assert response.status_code == 200
    assert response.json()["isActive"] is True


async def test_an_admin_cannot_block_themselves(
    client: httpx.AsyncClient, headers: dict[str, str], admin: User
) -> None:
    response = await client.post(
        f"{ADMIN}/customers/{admin.id}/active", headers=headers, json={"isActive": False}
    )

    # Recovering from this needs the CLI on the server.
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CANNOT_BLOCK_SELF"


async def test_an_admin_cannot_block_another_admin(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession
) -> None:
    other = await make_user(db, email="peer@voltbox.ge", role=ROLE_ADMIN)

    response = await client.post(
        f"{ADMIN}/customers/{other.id}/active", headers=headers, json={"isActive": False}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CANNOT_BLOCK_ADMIN"


@pytest.mark.parametrize("needle", ["+995 555 11 12 22", "555111222"])
async def test_customers_are_found_by_phone_however_it_is_typed(
    client: httpx.AsyncClient, headers: dict[str, str], db: AsyncSession, needle: str
) -> None:
    customer = await make_user(db, email=f"phone-{abs(hash(needle)) % 999}@example.ge")
    customer.phone = "555 11 12 22"
    await db.flush()

    response = await client.get(f"{ADMIN}/customers", headers=headers, params={"q": needle})

    assert str(customer.id) in [row["id"] for row in response.json()["items"]]
