"""Phase 6 — შეკვეთების ტესტები.

§10-ის სავალდებულო ნაკრები: ფასის გაყალბება იგნორირდება · overselling
შეუძლებელია პარალელურ პირობებში · სტუმრის checkout მუშაობს · გაუქმებისას
მარაგი ბრუნდება · ჯამები ცენტამდე ემთხვევა.
"""

from decimal import Decimal

import httpx
import pytest
from app.db.models import Product
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_brand, make_category, make_product

CUSTOMER = {
    "firstName": "გიორგი",
    "lastName": "ბერიძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
    "comment": "",
}


@pytest.fixture
async def shop(db: AsyncSession) -> dict[str, Product]:
    category = await make_category(db, "phones")
    brand = await make_brand(db, "Samsung")
    cheap = await make_product(
        db, category, brand, slug="cheap", name="Cheap Phone", price="40.00", stock=5
    )
    pricey = await make_product(
        db, category, brand, slug="pricey", name="Pricey Phone", price="200.00", stock=2
    )
    last_one = await make_product(
        db, category, brand, slug="last-one", name="Last One", price="99.99", stock=1
    )
    return {"cheap": cheap, "pricey": pricey, "last_one": last_one}


async def _place(
    client: httpx.AsyncClient, items: list[dict[str, object]], **kwargs: object
) -> httpx.Response:
    return await client.post(
        "/api/v1/orders",
        json={"items": items, "customer": CUSTOMER, "paymentMethod": "cash"},
        **kwargs,  # type: ignore[arg-type]
    )


async def test_guest_checkout_creates_an_order(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    response = await _place(client, [{"productId": str(shop["cheap"].id), "qty": 2}])

    assert response.status_code == 201
    body = response.json()
    assert body["orderNumber"].startswith("VB-")
    assert body["status"] == "pending"
    assert body["customer"]["firstName"] == "გიორგი"


async def test_totals_are_computed_from_database_prices(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    # 2 × 40.00 = 80.00 → 150-ზე ნაკლებია, მიწოდება 5.00
    body = (await _place(client, [{"productId": str(shop["cheap"].id), "qty": 2}])).json()

    assert body["totals"] == {"subtotal": "80.00", "shipping": "5.00", "total": "85.00"}


async def test_free_shipping_above_the_threshold(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    # 1 × 200.00 ≥ 150 → მიწოდება უფასოა
    body = (await _place(client, [{"productId": str(shop["pricey"].id), "qty": 1}])).json()

    assert body["totals"] == {"subtotal": "200.00", "shipping": "0.00", "total": "200.00"}


async def test_client_supplied_price_is_rejected(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    """ფასის გაყალბება ხმაურით უნდა ჩავარდეს და არა ჩუმად იგნორირდეს."""
    response = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"productId": str(shop["pricey"].id), "qty": 1, "price": "0.01"}],
            "customer": CUSTOMER,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_totals_in_the_body_are_rejected(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    response = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"productId": str(shop["cheap"].id), "qty": 1}],
            "customer": CUSTOMER,
            "totals": {"subtotal": "0.01", "shipping": "0", "total": "0.01"},
        },
    )

    assert response.status_code == 400


async def test_stock_is_decremented(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    await _place(client, [{"productId": str(shop["cheap"].id), "qty": 3}])

    stock = await db.scalar(select(Product.stock).where(Product.id == shop["cheap"].id))
    assert stock == 2


async def test_insufficient_stock_is_a_conflict(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    response = await _place(client, [{"productId": str(shop["last_one"].id), "qty": 5}])

    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "INSUFFICIENT_STOCK"
    assert body["details"]["available"] == 1
    assert body["details"]["productId"] == str(shop["last_one"].id)


async def test_unknown_product_is_not_found(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    response = await _place(
        client, [{"productId": "00000000-0000-0000-0000-000000000000", "qty": 1}]
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


async def test_the_same_product_twice_is_summed(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    """ერთი პროდუქტი ორ ხაზად — რაოდენობები უნდა შეიკრიბოს, თორემ მარაგის
    შემოწმება ორივე ხაზზე ცალკე გაივლიდა და overselling გახდებოდა შესაძლებელი."""
    response = await _place(
        client,
        [
            {"productId": str(shop["last_one"].id), "qty": 1},
            {"productId": str(shop["last_one"].id), "qty": 1},
        ],
    )

    assert response.status_code == 409


async def test_guest_order_requires_a_georgian_phone(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    response = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"productId": str(shop["cheap"].id), "qty": 1}],
            "customer": {**CUSTOMER, "phone": "123"},
        },
    )

    assert response.status_code == 400


async def test_quantity_above_the_cap_is_rejected(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    response = await _place(client, [{"productId": str(shop["cheap"].id), "qty": 100}])

    assert response.status_code == 400


async def test_idempotency_key_prevents_a_duplicate_order(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """ორმაგად დაჭერილი „შეკვეთის დადასტურება“ ორ შეკვეთას არ უნდა ქმნიდეს."""
    headers = {"Idempotency-Key": "checkout-123"}
    first = await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}], headers=headers)
    second = await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}], headers=headers)

    assert first.json()["orderNumber"] == second.json()["orderNumber"]
    stock = await db.scalar(select(Product.stock).where(Product.id == shop["cheap"].id))
    assert stock == 4  # ერთხელ ჩამოიწერა და არა ორჯერ


async def test_snapshot_survives_a_later_price_change(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    body = (await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}])).json()
    number = body["orderNumber"]

    shop["cheap"].price = Decimal("999.00")
    shop["cheap"].name = "Renamed"
    await db.flush()

    stored = (await client.get(f"/api/v1/orders/{number}", params={"email": "555123456"})).json()

    assert stored["items"][0]["snapshot"]["price"] == "40.00"
    assert stored["items"][0]["snapshot"]["name"] == "Cheap Phone"
    assert stored["totals"]["total"] == "45.00"


async def test_order_number_is_not_readable_without_the_contact(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    """ნომერი თანმიმდევრობითია და გამოცნობადი — მარტო ნომრით წვდომა დაუშვებელია."""
    number = (await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}])).json()[
        "orderNumber"
    ]

    anonymous = await client.get(f"/api/v1/orders/{number}")
    wrong_contact = await client.get(f"/api/v1/orders/{number}", params={"email": "555999999"})

    assert anonymous.status_code == 404
    assert wrong_contact.status_code == 404


async def test_authenticated_user_sees_only_their_own_orders(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    async def register(email: str) -> dict[str, str]:
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

    owner = await register("owner@example.ge")
    await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}], headers=owner)
    stranger = await register("stranger@example.ge")

    mine = await client.get("/api/v1/orders", headers=owner)
    theirs = await client.get("/api/v1/orders", headers=stranger)

    assert len(mine.json()) == 1
    assert theirs.json() == []
