"""Phase 6 — შეკვეთების ტესტები.

§10-ის სავალდებულო ნაკრები: ფასის გაყალბება იგნორირდება · overselling
შეუძლებელია პარალელურ პირობებში · სტუმრის checkout მუშაობს · გაუქმებისას
მარაგი ბრუნდება · ჯამები ცენტამდე ემთხვევა.
"""

import uuid
from decimal import Decimal

import httpx
import pytest
from app.core.rate_limit import LOOKUP_RATE_LIMIT, limiter
from app.db.models import ROLE_ADMIN, Order, Product, ProductImage
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

#: A real UUID: the API refuses anything else, because a key is a permanent
#: claim on a row and free text like "checkout" would replay forever.
KEY = "6f1c2f7e-6a3f-4f2e-8a1e-4d9f0b2c7a10"

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
    # The API refuses a checkout with no Idempotency-Key, so every call needs
    # one. It is fresh per call rather than a shared constant: a constant would
    # turn the second _place in a test into a replay of the first, and every
    # assertion after it would pass while testing nothing. A caller that brings
    # its own headers keeps them - its own key, or just an Authorization header,
    # in which case it still gets a key.
    caller_headers = kwargs.pop("headers", None)
    headers = {"Idempotency-Key": str(uuid.uuid4())}
    if isinstance(caller_headers, dict):
        headers.update(caller_headers)
    return await client.post(
        "/api/v1/orders",
        json={"items": items, "customer": CUSTOMER, "paymentMethod": "cash"},
        headers=headers,
        **kwargs,  # type: ignore[arg-type]
    )


async def _order_count(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(Order)) or 0)


async def test_guest_checkout_creates_an_order(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    response = await _place(client, [{"productId": str(shop["cheap"].id), "qty": 2}])

    assert response.status_code == 201
    body = response.json()
    assert body["orderNumber"].startswith("VB-")
    assert body["status"] == "pending"
    assert body["customer"]["firstName"] == "გიორგი"


async def test_the_ten_thousand_and_first_order_of_a_day_gets_a_number_of_its_own(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """The suffix is a global sequence modulo its width. At four digits this
    second order was given the first one's number and checkout answered 500.

    Both orders run in the fixture's one transaction, so `now()` - and the day
    it names - is the same for both. The sequence is not rolled back with the
    test, which only moves it further on.
    """
    item = [{"productId": str(shop["cheap"].id), "qty": 1}]

    first = await _place(client, item)
    # Ten thousand orders later, the same day.
    await db.execute(text("SELECT setval('order_number_seq', currval('order_number_seq') + 9999)"))
    second = await _place(client, item)

    assert second.status_code == 201, second.text
    assert second.json()["orderNumber"] != first.json()["orderNumber"]


async def test_totals_are_computed_from_database_prices(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    # 1 × 40.00 → 50-ზე ნაკლებია, თბილისში მიწოდება 8.00
    body = (await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}])).json()

    assert body["totals"] == {"subtotal": "40.00", "shipping": "8.00", "total": "48.00"}


async def test_free_shipping_above_the_threshold(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    # 1 × 200.00 ≥ 50 → მიწოდება უფასოა
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
    headers = {"Idempotency-Key": KEY}
    first = await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}], headers=headers)
    second = await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}], headers=headers)

    assert first.json()["orderNumber"] == second.json()["orderNumber"]
    # A replay looks exactly like the original, so the client needs no branch.
    assert second.json() == first.json()
    stock = await db.scalar(select(Product.stock).where(Product.id == shop["cheap"].id))
    assert stock == 4  # ერთხელ ჩამოიწერა და არა ორჯერ


async def test_a_key_cannot_be_used_to_read_somebody_elses_order(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    """The key is a value the client chooses, so a repeat has to prove who it is.

    Without the owner check, a guessed or copied key returns a stranger's name,
    address, phone number and basket.
    """
    headers = {"Idempotency-Key": KEY}
    await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}], headers=headers)

    stranger = dict(CUSTOMER, phone="599999999", firstName="ნინო")
    response = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"productId": str(shop["cheap"].id), "qty": 1}],
            "customer": stranger,
            "paymentMethod": "cash",
        },
        headers=headers,
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    # Nothing about the order it refused to show.
    assert "orderNumber" not in body
    assert "ბერიძე" not in response.text


async def test_a_guest_cannot_replay_an_order_placed_while_signed_in(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """An account's order belongs to the account, not to whoever knows the phone."""
    user = await make_user(db, email="owner@voltbox.ge")
    headers = {"Idempotency-Key": KEY}
    placed = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"productId": str(shop["cheap"].id), "qty": 1}],
            "customer": CUSTOMER,
            "paymentMethod": "cash",
        },
        headers={**headers, **auth_header(user)},
    )
    assert placed.status_code == 201

    # Same key, same contact details, but no longer signed in.
    response = await _place(
        client, [{"productId": str(shop["cheap"].id), "qty": 1}], headers=headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


async def test_the_same_email_written_differently_still_replays(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    """Case and stray spaces are not a different person.

    (The phone field is already constrained by the schema to nine digits, so
    at checkout it arrives in one shape; the free-form case is the lookup.)
    """
    headers = {"Idempotency-Key": KEY}
    with_email = dict(CUSTOMER, email="Giorgi@Example.GE")
    first = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"productId": str(shop["cheap"].id), "qty": 1}],
            "customer": with_email,
            "paymentMethod": "cash",
        },
        headers=headers,
    )
    assert first.status_code == 201

    response = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"productId": str(shop["cheap"].id), "qty": 1}],
            "customer": dict(with_email, email="  giorgi@example.ge  "),
            "paymentMethod": "cash",
        },
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["orderNumber"] == first.json()["orderNumber"]


async def test_a_checkout_without_a_key_is_refused(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """არარსებული გასაღები „replay არ მჭირდება“ არ არის — ეს დუბლიკატია.

    NULL NULL-ს არ ეჯახება, ამიტომ UNIQUE ინდექსი გამეორებულ მოთხოვნას
    გაატარებდა: მეორე შეკვეთა შეიქმნებოდა და მარაგი კიდევ ერთხელ ჩამოიწერებოდა.
    """
    response = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"productId": str(shop["cheap"].id), "qty": 1}],
            "customer": CUSTOMER,
            "paymentMethod": "cash",
        },
    )

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    # შეტყობინებამ უნდა თქვას რა გამოგზავნოს, და არა მხოლოდ ის, რომ რაღაც აკლია.
    assert "Idempotency-Key" in body["message"]
    assert "UUID" in body["message"]

    stock = await db.scalar(select(Product.stock).where(Product.id == shop["cheap"].id))
    assert stock == 5  # არაფერი ჩამოწერილა


@pytest.mark.parametrize("key", ["checkout-123", "not a uuid", "12345"])
async def test_a_key_that_is_not_a_uuid_is_refused(
    client: httpx.AsyncClient, shop: dict[str, Product], key: str
) -> None:
    response = await _place(
        client, [{"productId": str(shop["cheap"].id), "qty": 1}], headers={"Idempotency-Key": key}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IDEMPOTENCY_KEY"


async def test_snapshot_survives_a_later_price_change(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    body = (await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}])).json()
    number = body["orderNumber"]

    shop["cheap"].price = Decimal("999.00")
    shop["cheap"].name = "Renamed"
    await db.flush()

    stored = (await _lookup(client, number, CUSTOMER["phone"])).json()

    assert stored["items"][0]["snapshot"]["price"] == "40.00"
    assert stored["items"][0]["snapshot"]["name"] == "Cheap Phone"
    assert stored["totals"]["total"] == "48.00"


async def test_order_number_is_not_readable_without_the_contact(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    """ნომერი თანმიმდევრობითია და გამოცნობადი — მარტო ნომრით წვდომა დაუშვებელია."""
    number = (await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}])).json()[
        "orderNumber"
    ]

    anonymous = await client.get(f"/api/v1/orders/{number}")
    wrong_contact = await _lookup(client, number, "555999999")

    # GET is for signed-in callers only now, so a guest gets 401 there.
    assert anonymous.status_code == 401
    assert wrong_contact.status_code == 404


async def _lookup(client: httpx.AsyncClient, number: str, contact: str) -> httpx.Response:
    return await client.post(
        "/api/v1/orders/lookup", json={"orderNumber": number, "contact": contact}
    )


async def test_a_guest_reads_their_order_with_the_contact_in_the_body(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    number = (await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}])).json()[
        "orderNumber"
    ]

    response = await _lookup(client, number, CUSTOMER["phone"])

    assert response.status_code == 200
    assert response.json()["orderNumber"] == number


async def test_the_contact_is_matched_however_it_is_written(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    """A shopper typing their own number back rarely reproduces the digits exactly.

    This is the case the shared normaliser exists for: the checkout schema
    constrains the phone, the lookup cannot.
    """
    number = (await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}])).json()[
        "orderNumber"
    ]

    for written in ["555 12 34 56", "+995555123456", "(555) 12-34-56", "0555123456"]:
        response = await _lookup(client, number, written)
        assert response.status_code == 200, written


async def test_an_unknown_number_and_a_wrong_contact_are_indistinguishable(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    """Order numbers are sequential. A different answer would make them enumerable."""
    number = (await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}])).json()[
        "orderNumber"
    ]

    wrong_contact = await _lookup(client, number, "599000000")
    no_such_order = await _lookup(client, "VB-20200101-0001", CUSTOMER["phone"])

    assert wrong_contact.status_code == no_such_order.status_code == 404
    assert wrong_contact.json() == no_such_order.json()


async def test_the_contact_never_reaches_a_url(client: httpx.AsyncClient) -> None:
    """The regression itself: a phone number in the query string.

    From there it is written to the access log of every hop, to proxy logs and
    to the browser's own history - none of which are places a customer's phone
    number can be deleted from afterwards.
    """
    schema = (await client.get("/openapi.json")).json()

    lookup = schema["paths"]["/api/v1/orders/lookup"]["post"]
    assert "parameters" not in lookup or lookup["parameters"] == []

    read_one = schema["paths"]["/api/v1/orders/{order_number}"]["get"]
    query_params = [p for p in read_one.get("parameters", []) if p["in"] == "query"]
    assert query_params == []


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


async def test_the_guest_lookup_is_rate_limited(
    client: httpx.AsyncClient, shop: dict[str, Product]
) -> None:
    """Order numbers are guessable, so the contact is the only thing in the way.

    At the global 60/minute a single attacker holding a phone number walks a
    whole day of order numbers in about three hours and reads names, addresses
    and purchase histories. The endpoint carries its own limit.

    The limiter is off for the suite - a 5/minute auth limit would reject the
    third login any test performs - so it is switched on for this one test and
    the counters are cleared either side of it.
    """
    number = (await _place(client, [{"productId": str(shop["cheap"].id), "qty": 1}])).json()[
        "orderNumber"
    ]

    limiter.enabled = True
    limiter.reset()
    try:
        statuses = [
            (await _lookup(client, number, "599000000")).status_code
            for _ in range(int(LOOKUP_RATE_LIMIT.split("/")[0]) + 1)
        ]
    finally:
        limiter.reset()
        limiter.enabled = False

    # Every attempt is a wrong contact, so a 404 each until the limit bites.
    assert statuses[:-1] == [404] * (len(statuses) - 1)
    assert statuses[-1] == 429


async def test_the_limit_does_not_reach_the_signed_in_path(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """Reading your own orders is not a guessing game and is not throttled here."""
    user = await make_user(db, email="reader@voltbox.ge")
    headers = auth_header(user)
    placed = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"productId": str(shop["cheap"].id), "qty": 1}],
            "customer": CUSTOMER,
            "paymentMethod": "cash",
        },
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    number = placed.json()["orderNumber"]

    limiter.enabled = True
    limiter.reset()
    try:
        statuses = [
            (await client.get(f"/api/v1/orders/{number}", headers=headers)).status_code
            for _ in range(int(LOOKUP_RATE_LIMIT.split("/")[0]) + 1)
        ]
    finally:
        limiter.reset()
        limiter.enabled = False

    assert set(statuses) == {200}


async def test_the_order_snapshots_the_primary_image_not_the_first_one(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """The two can disagree, and the order keeps whichever it took, forever.

    `is_primary` is a partial unique index, not a rule about ordering, so an
    admin who reorders images without touching the primary makes position 0 and
    the primary two different photos. The order must carry the one the customer
    was looking at.
    """
    product = shop["cheap"]
    await db.execute(delete(ProductImage).where(ProductImage.product_id == product.id))
    db.add_all(
        [
            ProductImage(product_id=product.id, url="/second.jpg", position=0, is_primary=False),
            ProductImage(product_id=product.id, url="/hero.jpg", position=1, is_primary=True),
        ]
    )
    await db.flush()

    body = (await _place(client, [{"productId": str(product.id), "qty": 1}])).json()

    assert body["items"][0]["snapshot"]["image"] == "/hero.jpg"


async def test_a_signed_in_customer_cannot_read_another_ones_order(
    client: httpx.AsyncClient, shop: dict[str, Product], db: AsyncSession
) -> None:
    """The list is scoped by user; reading one by number has to be too.

    Order numbers are sequential and therefore guessable, so `GET /orders/{n}`
    being behind a login proves nothing on its own - every customer has one.
    """
    owner = await make_user(db, email="owner-by-number@example.ge")
    stranger = await make_user(db, email="stranger-by-number@example.ge")

    placed = await _place(
        client, [{"productId": str(shop["cheap"].id), "qty": 1}], headers=auth_header(owner)
    )
    number = placed.json()["orderNumber"]

    mine = await client.get(f"/api/v1/orders/{number}", headers=auth_header(owner))
    theirs = await client.get(f"/api/v1/orders/{number}", headers=auth_header(stranger))

    assert mine.status_code == 200
    assert mine.json()["orderNumber"] == number
    # Not 403: telling them the order exists is already more than they had.
    assert theirs.status_code == 404
    assert theirs.json()["error"]["code"] == "ORDER_NOT_FOUND"


async def test_knowing_the_contact_does_not_open_the_signed_in_route(
    client: httpx.AsyncClient, shop: dict[str, Product], db: AsyncSession
) -> None:
    """`GET /orders/{n}` takes no contact, so learning one must not help.

    The guest path exists for exactly this and is rate limited; this route is
    ownership only, and must not quietly become a second way in.
    """
    owner = await make_user(db, email="owner-contact@example.ge")
    stranger = await make_user(db, email="stranger-contact@example.ge")

    placed = await _place(
        client, [{"productId": str(shop["cheap"].id), "qty": 1}], headers=auth_header(owner)
    )
    number = placed.json()["orderNumber"]

    # The phone the order was actually placed with, offered every way the route
    # could conceivably read one.
    response = await client.get(
        f"/api/v1/orders/{number}?contact={CUSTOMER['phone']}",
        headers={**auth_header(stranger), "X-Contact": CUSTOMER["phone"]},
    )

    assert response.status_code == 404


class TestPaymentMethod:
    """Only the ways this shop can actually be paid.

    Both stored values mean "on delivery" - there is no online payment - so
    nothing here moves money and a made-up value could not steal anything. What
    it could do is arrive in the admin panel reading "already paid" beside an
    order that is not, which is a courier handing goods over for nothing.

    `status` has had an enum since the first migration. This is the same idea
    applied to the other field an operator acts on, and it was free text from
    the request body all the way to the order list.

    Card to the courier is no longer offered. New orders are refused it; orders
    already stored with it keep it and must still load.
    """

    async def test_cash_is_accepted(
        self, client: httpx.AsyncClient, shop: dict[str, Product]
    ) -> None:
        response = await client.post(
            "/api/v1/orders",
            json={
                "items": [{"productId": str(shop["cheap"].id), "qty": 1}],
                "customer": CUSTOMER,
                "paymentMethod": "cash",
            },
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 201
        assert response.json()["paymentMethod"] == "cash"

    async def test_card_to_the_courier_is_refused_on_a_new_order(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        response = await client.post(
            "/api/v1/orders",
            json={
                "items": [{"productId": str(shop["cheap"].id), "qty": 1}],
                "customer": CUSTOMER,
                "paymentMethod": "card_on_delivery",
            },
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert "paymentMethod" in str(error["details"])
        assert await _order_count(db) == 0

    async def test_an_old_order_paid_by_card_still_loads(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        """Stored before the method was withdrawn: the owner and the admin read it."""
        owner = await make_user(db, email="card@example.ge")
        admin = await make_user(db, email="admin@example.ge", role=ROLE_ADMIN)
        order = Order(
            order_number="VB-20260901-00001",
            user_id=owner.id,
            status="delivered",
            customer={
                "first_name": "გიორგი",
                "last_name": "ბერიძე",
                "phone": "555123456",
                "city": "ბათუმი",
                "address": "რუსთაველის ქუჩა 1",
            },
            shipping_address={"city": "ბათუმი", "address": "რუსთაველის ქუჩა 1"},
            subtotal=Decimal("80.00"),
            shipping=Decimal("5.00"),
            total=Decimal("85.00"),
            payment_method="card_on_delivery",
        )
        db.add(order)
        await db.flush()

        listed = await client.get("/api/v1/orders", headers=auth_header(owner))
        one = await client.get(f"/api/v1/orders/{order.order_number}", headers=auth_header(owner))
        admin_view = await client.get(
            f"/api/v1/admin/orders/{order.id}", headers=auth_header(admin)
        )

        assert listed.status_code == 200, listed.text
        assert [o["paymentMethod"] for o in listed.json()] == ["card_on_delivery"]
        assert one.status_code == 200, one.text
        assert one.json()["paymentMethod"] == "card_on_delivery"
        # Kept as stored: the old flat fee and a city no longer served.
        assert one.json()["totals"] == {"subtotal": "80.00", "shipping": "5.00", "total": "85.00"}
        assert admin_view.status_code == 200, admin_view.text
        assert admin_view.json()["paymentMethod"] == "card_on_delivery"
        assert admin_view.json()["shipping"] == "5.00"

    @pytest.mark.parametrize(
        "method",
        ["already paid", "bank_transfer", "CASH", "", "crypto", "cash "],
    )
    async def test_anything_else_is_refused(
        self, client: httpx.AsyncClient, shop: dict[str, Product], method: str
    ) -> None:
        response = await client.post(
            "/api/v1/orders",
            json={
                "items": [{"productId": str(shop["cheap"].id), "qty": 1}],
                "customer": CUSTOMER,
                "paymentMethod": method,
            },
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_the_database_refuses_it_too(
        self, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        """The schema is one half; this is the half that survives new code.

        A second way of creating an order - a script, an admin action, a future
        endpoint - would not go through CreateOrderRequest.
        """
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            await db.execute(
                text(
                    "INSERT INTO orders (id, order_number, status, payment_method, "
                    "subtotal, shipping, total, customer, guest_phone) "
                    "VALUES (gen_random_uuid(), 'VB-TEST-0001', 'pending', 'already paid', "
                    "0, 0, 0, '{}'::jsonb, '555123456')"
                )
            )
        await db.rollback()


class TestDelivery:
    """The fee comes from the city and the goods, and from nothing the client says.

    The owner's rules: Tbilisi 8, Rustavi 5, free from 50 of goods, and no other
    city. They live in app/services/delivery.py; these tests write the numbers
    out rather than reading them from there, so a change to the table has to
    change a test too.
    """

    @staticmethod
    async def _checkout(
        client: httpx.AsyncClient, product: Product, **overrides: object
    ) -> httpx.Response:
        body: dict[str, object] = {
            "items": [{"productId": str(product.id), "qty": 1}],
            "customer": CUSTOMER,
            "paymentMethod": "cash",
        }
        body.update(overrides)
        return await client.post(
            "/api/v1/orders", json=body, headers={"Idempotency-Key": str(uuid.uuid4())}
        )

    @pytest.mark.parametrize(
        ("city", "fee", "total"),
        [("თბილისი", "8.00", "48.00"), ("რუსთავი", "5.00", "45.00")],
    )
    async def test_each_city_pays_its_own_fee(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        shop: dict[str, Product],
        city: str,
        fee: str,
        total: str,
    ) -> None:
        response = await self._checkout(client, shop["cheap"], customer={**CUSTOMER, "city": city})

        assert response.status_code == 201, response.text
        assert response.json()["totals"] == {"subtotal": "40.00", "shipping": fee, "total": total}
        # Stored apart from the goods, and the total includes it.
        stored = await db.scalar(
            select(Order).where(Order.order_number == response.json()["orderNumber"])
        )
        assert stored is not None
        assert (stored.subtotal, stored.shipping, stored.total) == (
            Decimal("40.00"),
            Decimal(fee),
            Decimal(total),
        )

    @pytest.mark.parametrize("city", ["თბილისი", "რუსთავი"])
    @pytest.mark.parametrize(
        ("price", "free"),
        [("50.00", True), ("49.99", False)],
        ids=["exactly-50-is-free", "one-tetri-below-is-charged"],
    )
    async def test_the_threshold_is_fifty_inclusive(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        shop: dict[str, Product],
        city: str,
        price: str,
        free: bool,
    ) -> None:
        product = await make_product(
            db,
            await make_category(db, "edge"),
            await make_brand(db, "Edge"),
            slug=f"edge-{price}",
            name=f"Edge {price}",
            price=price,
            stock=1,
        )

        response = await self._checkout(client, product, customer={**CUSTOMER, "city": city})

        assert response.status_code == 201, response.text
        shipping = Decimal(response.json()["totals"]["shipping"])
        fees = {"თბილისი": Decimal("8"), "რუსთავი": Decimal("5")}
        expected = Decimal("0") if free else fees[city]
        assert shipping == expected
        assert Decimal(response.json()["totals"]["total"]) == Decimal(price) + expected

    @pytest.mark.parametrize(
        "where",
        [
            {"shipping": "0.00"},
            {"deliveryFee": "0.00"},
            {"totals": {"subtotal": "40.00", "shipping": "0.00", "total": "40.00"}},
            {"customer": {**CUSTOMER, "shipping": "0.00"}},
        ],
        ids=["shipping", "deliveryFee", "totals", "inside-customer"],
    )
    async def test_a_client_supplied_fee_never_reaches_the_order(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        shop: dict[str, Product],
        where: dict[str, object],
    ) -> None:
        """Refused, like a client-supplied price - never used, never stored.

        Refused rather than dropped: `extra="forbid"` makes a contract
        regression loud. Either way the fee a client names cannot become the
        fee an order carries, which is the property that matters here.
        """
        before = await _order_count(db)

        response = await self._checkout(client, shop["cheap"], **where)

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert await _order_count(db) == before

    async def test_the_fee_is_the_servers_even_when_the_client_sends_none(
        self, client: httpx.AsyncClient, shop: dict[str, Product]
    ) -> None:
        """The other half: a body with no fee at all is charged the city's."""
        response = await self._checkout(client, shop["cheap"])

        assert response.json()["totals"]["shipping"] == "8.00"

    @pytest.mark.parametrize("city", ["ბათუმი", "ქუთაისი", "Tbilisi", "თბილისი, ვაკე"])
    async def test_a_city_the_shop_does_not_serve_is_refused(
        self,
        client: httpx.AsyncClient,
        db: AsyncSession,
        shop: dict[str, Product],
        city: str,
    ) -> None:
        before = await _order_count(db)

        response = await self._checkout(client, shop["cheap"], customer={**CUSTOMER, "city": city})

        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "CITY_NOT_SERVED"
        assert error["details"] == [{"field": "customer.city", "cities": ["თბილისი", "რუსთავი"]}]
        assert await _order_count(db) == before
        stock = await db.scalar(select(Product.stock).where(Product.id == shop["cheap"].id))
        assert stock == 5

    async def test_the_storefront_reads_the_same_rules(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/api/v1/delivery")

        assert response.status_code == 200
        assert response.json() == {
            "cities": [{"name": "თბილისი", "fee": "8.00"}, {"name": "რუსთავი", "fee": "5.00"}],
            "freeFrom": "50.00",
            "currency": "GEL",
        }
