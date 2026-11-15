"""Phase 5 — მისამართების ტესტები: CRUD, მფლობელობა, ერთი ძირითადი."""

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from app.db.models import Address, User
from app.db.session import engine
from app.services.address import MAX_ADDRESSES_PER_USER
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_user

ADDRESS = {"label": "სახლი", "city": "თბილისი", "address": "ჭავჭავაძის გამზირი 42"}


async def _register(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "firstName": "ნინო",
            "lastName": "კაპანაძე",
            "email": email,
            "password": "supersecret1",
        },
    )
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def test_addresses_require_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/addresses")

    assert response.status_code == 401


async def test_create_returns_the_full_list(client: httpx.AsyncClient) -> None:
    headers = await _register(client, "a@example.ge")

    response = await client.post("/api/v1/addresses", headers=headers, json=ADDRESS)

    assert response.status_code == 201
    body = response.json()
    assert len(body) == 1
    assert body[0]["city"] == "თბილისი"
    assert body[0]["address"] == "ჭავჭავაძის გამზირი 42"


async def test_setting_a_new_default_clears_the_previous_one(
    client: httpx.AsyncClient,
) -> None:
    """ბაზაში partial unique ინდექსია — გასუფთავება იმავე ტრანზაქციაში უნდა მოხდეს."""
    headers = await _register(client, "b@example.ge")
    await client.post("/api/v1/addresses", headers=headers, json={**ADDRESS, "isDefault": True})

    body = (
        await client.post(
            "/api/v1/addresses",
            headers=headers,
            json={**ADDRESS, "city": "ბათუმი", "isDefault": True},
        )
    ).json()

    defaults = [a for a in body if a["isDefault"]]
    assert len(defaults) == 1
    assert defaults[0]["city"] == "ბათუმი"


async def test_update_replaces_the_address(client: httpx.AsyncClient) -> None:
    headers = await _register(client, "c@example.ge")
    created = (await client.post("/api/v1/addresses", headers=headers, json=ADDRESS)).json()

    response = await client.put(
        f"/api/v1/addresses/{created[0]['id']}",
        headers=headers,
        json={**ADDRESS, "city": "ქუთაისი"},
    )

    assert response.status_code == 200
    assert response.json()[0]["city"] == "ქუთაისი"


async def test_delete_removes_the_address(client: httpx.AsyncClient) -> None:
    headers = await _register(client, "d@example.ge")
    created = (await client.post("/api/v1/addresses", headers=headers, json=ADDRESS)).json()

    response = await client.delete(f"/api/v1/addresses/{created[0]['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_another_users_address_is_reported_as_missing(
    client: httpx.AsyncClient,
) -> None:
    """404 და არა 403 — 403 ამხელდა, რომ ასეთი id არსებობს."""
    owner = await _register(client, "owner@example.ge")
    created = (await client.post("/api/v1/addresses", headers=owner, json=ADDRESS)).json()
    intruder = await _register(client, "intruder@example.ge")

    read = await client.put(f"/api/v1/addresses/{created[0]['id']}", headers=intruder, json=ADDRESS)
    removed = await client.delete(f"/api/v1/addresses/{created[0]['id']}", headers=intruder)

    assert read.status_code == 404
    assert removed.status_code == 404
    assert read.json()["error"]["code"] == "ADDRESS_NOT_FOUND"


async def test_addresses_are_scoped_to_the_owner(client: httpx.AsyncClient) -> None:
    owner = await _register(client, "one@example.ge")
    await client.post("/api/v1/addresses", headers=owner, json=ADDRESS)
    other = await _register(client, "two@example.ge")

    response = await client.get("/api/v1/addresses", headers=other)

    assert response.json() == []


async def test_short_address_is_rejected(client: httpx.AsyncClient) -> None:
    headers = await _register(client, "e@example.ge")

    response = await client.post(
        "/api/v1/addresses", headers=headers, json={**ADDRESS, "address": "ა"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def _fill(db: AsyncSession, user: User, count: int) -> None:
    """`count` plain addresses written straight to the table, none of them a default."""
    db.add_all(
        Address(user_id=user.id, label=f"a{n}", city="Tbilisi", address_line="Chavchavadze 42")
        for n in range(count)
    )
    await db.flush()


async def _held(db: AsyncSession, user: User) -> int:
    held = await db.scalar(
        select(func.count()).select_from(Address).where(Address.user_id == user.id)
    )
    return held or 0


async def test_an_account_can_hold_exactly_the_limit(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    user = await make_user(db)
    await _fill(db, user, MAX_ADDRESSES_PER_USER - 1)

    response = await client.post("/api/v1/addresses", headers=auth_header(user), json=ADDRESS)

    assert response.status_code == 201
    assert len(response.json()) == MAX_ADDRESSES_PER_USER


async def test_the_address_past_the_limit_is_refused_and_nothing_is_written(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    user = await make_user(db)
    headers = auth_header(user)
    await _fill(db, user, MAX_ADDRESSES_PER_USER)

    for is_default in (False, True):
        response = await client.post(
            "/api/v1/addresses", headers=headers, json={**ADDRESS, "isDefault": is_default}
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ADDRESS_LIMIT_REACHED"
        assert await _held(db, user) == MAX_ADDRESSES_PER_USER


async def test_deleting_an_address_makes_room_again(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    user = await make_user(db)
    headers = auth_header(user)
    await _fill(db, user, MAX_ADDRESSES_PER_USER)
    listed = (await client.get("/api/v1/addresses", headers=headers)).json()
    assert len(listed) == MAX_ADDRESSES_PER_USER

    removed = await client.delete(f"/api/v1/addresses/{listed[0]['id']}", headers=headers)
    created = await client.post("/api/v1/addresses", headers=headers, json=ADDRESS)

    assert removed.status_code == 200
    assert created.status_code == 201
    assert len(created.json()) == MAX_ADDRESSES_PER_USER


async def test_the_limit_is_per_account(client: httpx.AsyncClient, db: AsyncSession) -> None:
    full = await make_user(db, email="full@example.ge")
    other = await make_user(db, email="other@example.ge")
    await _fill(db, full, MAX_ADDRESSES_PER_USER)

    response = await client.post("/api/v1/addresses", headers=auth_header(other), json=ADDRESS)

    assert response.status_code == 201


@pytest.fixture
def statements() -> Iterator[list[str]]:
    """Every SQL statement sent to the database while the test runs."""
    seen: list[str] = []

    def record(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        seen.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)


async def test_authenticating_a_request_is_one_statement_whatever_the_addresses(
    client: httpx.AsyncClient, db: AsyncSession, statements: list[str]
) -> None:
    """The account's addresses used to be loaded with it, on every request."""
    user = await make_user(db)
    headers = auth_header(user)
    await _fill(db, user, MAX_ADDRESSES_PER_USER)
    statements.clear()

    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    assert len(statements) == 1, statements
    assert "FROM users" in statements[0]


async def test_deleting_an_account_through_the_orm_takes_its_addresses_with_it(
    db: AsyncSession,
) -> None:
    """`addresses` is lazy="raise": the cascade must be the database's, not a load."""
    user = await make_user(db)
    await _fill(db, user, 3)
    db.expire(user)

    await db.delete(user)
    await db.flush()

    assert await db.scalar(select(func.count()).select_from(Address)) == 0
