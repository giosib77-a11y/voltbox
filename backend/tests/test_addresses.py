"""Phase 5 — მისამართების ტესტები: CRUD, მფლობელობა, ერთი ძირითადი."""

import httpx

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
