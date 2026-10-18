"""The saved cart.

What it covers: that a signed-in cart follows the person between devices, that
prices come from the catalogue rather than from whatever the client sent, and
that signing in with a basket already in the browser does not double an order.

The merge rule is the part worth pinning. Taking the larger quantity rather than
the sum is a judgement - two cables added on a phone and two on a laptop is one
person meaning two - and summing would be the kind of change that looks harmless
in review and charges somebody twice.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import jwt
import pytest
from app.core.config import settings
from app.core.rate_limit import CART_QUOTE_RATE_LIMIT, limiter
from app.core.security import VERSION_CLAIM
from app.db.models import Cart, Product
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

CART = "/api/v1/cart"
QUOTE = CART + "/quote"


@pytest.fixture
async def shop(db: AsyncSession) -> dict[str, Product]:
    category = await make_category(db, "phones")
    brand = await make_brand(db, "Samsung")
    return {
        "cable": await make_product(
            db, category, brand, slug="cable", name="Cable", price="10.00", stock=20
        ),
        "charger": await make_product(
            db, category, brand, slug="charger", name="Charger", price="45.50", stock=5
        ),
        "phone": await make_product(
            db, category, brand, slug="phone", name="Phone", price="999.99", stock=2
        ),
    }


def _lines(*pairs: tuple[Product, int]) -> dict[str, object]:
    return {"items": [{"productId": str(product.id), "qty": qty} for product, qty in pairs]}


async def test_a_saved_cart_comes_back(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """The whole point: put it in here, find it there."""
    user = await make_user(db, email="saver@example.ge")
    headers = auth_header(user)

    await client.put(CART, headers=headers, json=_lines((shop["cable"], 2)))
    read_back = await client.get(CART, headers=headers)

    assert read_back.status_code == 200
    items = read_back.json()["items"]
    assert len(items) == 1
    assert items[0]["productId"] == str(shop["cable"].id)
    assert items[0]["qty"] == 2


async def test_the_price_comes_from_the_catalogue_not_the_client(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """A cart is a list of intentions; the price beside each is today's.

    Storing what the browser sent would mean serving a month-old price from the
    server as though it were current.
    """
    user = await make_user(db, email="pricing@example.ge")
    headers = auth_header(user)
    await client.put(CART, headers=headers, json=_lines((shop["charger"], 1)))

    shop["charger"].price = "39.99"  # type: ignore[assignment]
    await db.flush()

    items = (await client.get(CART, headers=headers)).json()["items"]

    assert items[0]["snapshot"]["price"] == "39.99"


async def test_an_unknown_field_in_a_line_is_refused(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """`extra="forbid"` again: a price sent here must not pass silently."""
    user = await make_user(db, email="extra@example.ge")

    response = await client.put(
        CART,
        headers=auth_header(user),
        json={"items": [{"productId": str(shop["cable"].id), "qty": 1, "price": "0.01"}]},
    )

    assert response.status_code == 400


async def test_replacing_really_replaces(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    user = await make_user(db, email="replace@example.ge")
    headers = auth_header(user)
    await client.put(CART, headers=headers, json=_lines((shop["cable"], 3)))

    await client.put(CART, headers=headers, json=_lines((shop["charger"], 1)))

    items = (await client.get(CART, headers=headers)).json()["items"]
    assert [i["productId"] for i in items] == [str(shop["charger"].id)]


async def test_saving_twice_does_not_create_two_carts(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    """One row per account, enforced by the database and not by hoping."""
    user = await make_user(db, email="once@example.ge")
    headers = auth_header(user)

    await client.put(CART, headers=headers, json=_lines((shop["cable"], 1)))
    await client.put(CART, headers=headers, json=_lines((shop["cable"], 2)))

    carts = (await db.scalars(select(Cart).where(Cart.user_id == user.id))).all()
    assert len(carts) == 1


async def test_clearing_empties_it(
    client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
) -> None:
    user = await make_user(db, email="clear@example.ge")
    headers = auth_header(user)
    await client.put(CART, headers=headers, json=_lines((shop["cable"], 1)))

    response = await client.delete(CART, headers=headers)

    assert response.status_code == 204
    assert (await client.get(CART, headers=headers)).json()["items"] == []


class TestMerging:
    """Signing in with a basket already in the browser."""

    async def test_the_larger_quantity_wins_rather_than_the_sum(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        """The judgement this whole feature turns on.

        Two cables added on a phone and two on a laptop is one person meaning
        two. Summing would hand them four at the moment they are least likely
        to re-read the basket.
        """
        user = await make_user(db, email="merger@example.ge")
        headers = auth_header(user)
        await client.put(CART, headers=headers, json=_lines((shop["cable"], 2)))

        merged = await client.post(
            CART + "/merge", headers=headers, json=_lines((shop["cable"], 2))
        )

        assert merged.status_code == 200
        assert merged.json()["items"][0]["qty"] == 2

    async def test_a_bigger_basket_here_wins(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        user = await make_user(db, email="bigger@example.ge")
        headers = auth_header(user)
        await client.put(CART, headers=headers, json=_lines((shop["cable"], 1)))

        merged = await client.post(
            CART + "/merge", headers=headers, json=_lines((shop["cable"], 4))
        )

        assert merged.json()["items"][0]["qty"] == 4

    async def test_a_bigger_basket_saved_wins(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        user = await make_user(db, email="saved-bigger@example.ge")
        headers = auth_header(user)
        await client.put(CART, headers=headers, json=_lines((shop["cable"], 7)))

        merged = await client.post(
            CART + "/merge", headers=headers, json=_lines((shop["cable"], 2))
        )

        assert merged.json()["items"][0]["qty"] == 7

    async def test_products_in_only_one_of_them_are_all_kept(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        user = await make_user(db, email="union@example.ge")
        headers = auth_header(user)
        await client.put(CART, headers=headers, json=_lines((shop["cable"], 1)))

        merged = await client.post(
            CART + "/merge", headers=headers, json=_lines((shop["charger"], 1))
        )

        assert {i["productId"] for i in merged.json()["items"]} == {
            str(shop["cable"].id),
            str(shop["charger"].id),
        }

    async def test_merging_into_nothing_just_saves(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        """The ordinary case: first sign-in on a new account."""
        user = await make_user(db, email="first@example.ge")

        merged = await client.post(
            CART + "/merge", headers=auth_header(user), json=_lines((shop["phone"], 1))
        )

        assert merged.json()["items"][0]["qty"] == 1


class TestProductsThatWentAway:
    """A cart outlives the catalogue it points at."""

    async def test_an_archived_product_drops_out_of_the_cart(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        user = await make_user(db, email="archived@example.ge")
        headers = auth_header(user)
        await client.put(CART, headers=headers, json=_lines((shop["cable"], 1), (shop["phone"], 1)))

        shop["cable"].archived_at = datetime.now(UTC)
        await db.flush()

        items = (await client.get(CART, headers=headers)).json()["items"]

        # The line is gone; the rest of the basket is not.
        assert [i["productId"] for i in items] == [str(shop["phone"].id)]

    async def test_a_deleted_product_does_not_break_reading_the_cart(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        """No foreign key, on purpose - so this is a missing line, not an error."""
        user = await make_user(db, email="ghost@example.ge")
        headers = auth_header(user)
        await client.put(CART, headers=headers, json=_lines((shop["cable"], 1)))

        await db.delete(shop["cable"])
        await db.flush()

        response = await client.get(CART, headers=headers)

        assert response.status_code == 200
        assert response.json()["items"] == []


class TestNobodyElsesCart:
    async def test_the_cart_needs_a_login(self, client: httpx.AsyncClient) -> None:
        for method in ("GET", "PUT", "DELETE"):
            response = await client.request(method, CART, json={"items": []})
            assert response.status_code == 401, method

    async def test_two_accounts_keep_separate_carts(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        mine = await make_user(db, email="mine@example.ge")
        theirs = await make_user(db, email="theirs@example.ge")

        await client.put(CART, headers=auth_header(mine), json=_lines((shop["cable"], 3)))

        assert (await client.get(CART, headers=auth_header(theirs))).json()["items"] == []


class TestQuote:
    """`POST /cart/quote`: a guest's cart priced from the catalogue as it is now.

    The guest cart lives in localStorage with a snapshot taken when the product
    was added; this is how checkout learns what the server will actually charge.
    """

    async def test_a_guest_gets_current_prices_stock_and_names(
        self, client: httpx.AsyncClient, shop: dict[str, Product]
    ) -> None:
        response = await client.post(
            QUOTE, json=_lines((shop["cable"], 2), (shop["phone"], 1)), params={"lang": "ka"}
        )

        assert response.status_code == 200
        by_id = {line["productId"]: line for line in response.json()["items"]}
        assert set(by_id) == {str(shop["cable"].id), str(shop["phone"].id)}
        cable = by_id[str(shop["cable"].id)]
        assert cable["qty"] == 2
        assert cable["snapshot"] == {
            "name": "Cable",
            "slug": "cable",
            "image": "/images/cable-1.svg",
            "price": "10.00",
            "oldPrice": None,
            "stock": 20,
        }
        assert by_id[str(shop["phone"].id)]["snapshot"]["price"] == "999.99"
        assert by_id[str(shop["phone"].id)]["snapshot"]["stock"] == 2

    async def test_a_price_changed_since_comes_back_changed(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        """The finding itself: 999 on Monday, 1099 on Wednesday."""
        body = _lines((shop["phone"], 1))
        first = await client.post(QUOTE, json=body)

        shop["phone"].price = Decimal("1099.00")
        shop["phone"].old_price = Decimal("1199.00")
        shop["phone"].stock = 1
        await db.flush()
        second = await client.post(QUOTE, json=body)

        assert first.json()["items"][0]["snapshot"]["price"] == "999.99"
        snapshot = second.json()["items"][0]["snapshot"]
        assert snapshot["price"] == "1099.00"
        assert snapshot["oldPrice"] == "1199.00"
        assert snapshot["stock"] == 1

    async def test_archived_inactive_and_unknown_products_are_absent(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        shop["cable"].archived_at = datetime.now(UTC)
        shop["charger"].is_active = False
        await db.flush()
        body = _lines((shop["cable"], 1), (shop["charger"], 1), (shop["phone"], 1))
        body["items"].append({"productId": str(uuid.uuid4()), "qty": 1})  # type: ignore[attr-defined]

        response = await client.post(QUOTE, json=body)

        assert response.status_code == 200
        assert [i["productId"] for i in response.json()["items"]] == [str(shop["phone"].id)]

    async def test_an_empty_basket_is_an_empty_answer(self, client: httpx.AsyncClient) -> None:
        response = await client.post(QUOTE, json={"items": []})

        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_the_name_follows_the_language_of_the_page(
        self, client: httpx.AsyncClient, db: AsyncSession
    ) -> None:
        category = await make_category(db, "audio")
        brand = await make_brand(db, "Sony")
        speaker = await make_product(
            db, category, brand, slug="speaker", name="დინამიკი", name_en="Speaker"
        )
        body = _lines((speaker, 1))

        english = await client.post(QUOTE, json=body, params={"lang": "en"})
        georgian = await client.post(QUOTE, json=body, params={"lang": "ka"})

        assert english.json()["items"][0]["snapshot"]["name"] == "Speaker"
        assert georgian.json()["items"][0]["snapshot"]["name"] == "დინამიკი"

    @pytest.mark.parametrize("excess", ["lines", "quantity", "unknown_field"])
    async def test_a_basket_checkout_would_refuse_is_refused(
        self, client: httpx.AsyncClient, shop: dict[str, Product], excess: str
    ) -> None:
        """The same bounds as the saved cart: 20 lines, 10 of a product, nothing extra."""
        line = {"productId": str(shop["cable"].id), "qty": 1}
        body: dict[str, object] = {
            "lines": {"items": [{"productId": str(uuid.uuid4()), "qty": 1} for _ in range(21)]},
            "quantity": {"items": [{**line, "qty": 11}]},
            "unknown_field": {"items": [{**line, "price": "0.01"}]},
        }[excess]  # type: ignore[assignment]

        response = await client.post(QUOTE, json=body)

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_the_largest_basket_checkout_takes_is_accepted(
        self, client: httpx.AsyncClient, shop: dict[str, Product]
    ) -> None:
        body = {"items": [{"productId": str(uuid.uuid4()), "qty": 10} for _ in range(20)]}

        assert (await client.post(QUOTE, json=body)).status_code == 200

    @pytest.mark.parametrize("kind", ["garbage", "expired"])
    async def test_a_bad_token_does_not_turn_a_guest_into_a_401(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product], kind: str
    ) -> None:
        """A guest whose session lapsed still has a cart to price."""
        if kind == "garbage":
            token = "not.a.token"
        else:
            user = await make_user(db, email="lapsed@example.ge")
            now = datetime.now(UTC)
            token = jwt.encode(
                {
                    "sub": str(user.id),
                    "iat": int((now - timedelta(days=2)).timestamp()),
                    "exp": int((now - timedelta(days=1)).timestamp()),
                    "jti": uuid.uuid4().hex,
                    VERSION_CLAIM: user.token_version,
                    "type": "access",
                },
                settings.jwt_secret.get_secret_value(),
                algorithm=settings.jwt_algorithm,
            )

        response = await client.post(
            QUOTE, headers={"Authorization": f"Bearer {token}"}, json=_lines((shop["cable"], 1))
        )

        assert response.status_code == 200
        assert len(response.json()["items"]) == 1

    async def test_it_writes_nothing(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        """No Cart row for a guest, and none for a signed-in caller either."""
        user = await make_user(db, email="reader@example.ge")

        await client.post(QUOTE, json=_lines((shop["cable"], 1)))
        await client.post(QUOTE, headers=auth_header(user), json=_lines((shop["cable"], 1)))

        assert (await db.scalars(select(Cart))).all() == []

    async def test_it_does_not_touch_a_saved_cart(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        user = await make_user(db, email="keeper@example.ge")
        headers = auth_header(user)
        await client.put(CART, headers=headers, json=_lines((shop["cable"], 3)))

        await client.post(QUOTE, headers=headers, json=_lines((shop["phone"], 1)))

        items = (await client.get(CART, headers=headers)).json()["items"]
        assert [(i["productId"], i["qty"]) for i in items] == [(str(shop["cable"].id), 3)]

    async def test_it_is_rate_limited_per_address(
        self, client: httpx.AsyncClient, shop: dict[str, Product]
    ) -> None:
        """A guest opening the cart or checkout is fine; a catalogue scraper meets 429.

        The limiter is off for the suite, so it is switched on for this one test
        and the counters are cleared either side of it.
        """
        allowed = int(CART_QUOTE_RATE_LIMIT.split("/")[0])
        body = _lines((shop["cable"], 1))

        limiter.enabled = True
        limiter.reset()
        try:
            statuses = [
                (await client.post(QUOTE, json=body)).status_code for _ in range(allowed + 1)
            ]
        finally:
            limiter.reset()
            limiter.enabled = False

        assert allowed == 30
        assert statuses == [200] * allowed + [429]


class TestLimits:
    async def test_a_quantity_above_the_cap_is_refused(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        user = await make_user(db, email="greedy@example.ge")

        response = await client.put(
            CART,
            headers=auth_header(user),
            json={"items": [{"productId": str(shop["cable"].id), "qty": 100}]},
        )

        assert response.status_code == 400

    async def test_too_many_different_products_is_refused(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        """A stored document must not be growable without bound."""
        user = await make_user(db, email="hoarder@example.ge")

        response = await client.put(
            CART,
            headers=auth_header(user),
            json={"items": [{"productId": str(uuid.uuid4()), "qty": 1} for _ in range(51)]},
        )

        assert response.status_code == 400

    async def test_the_cart_holds_what_checkout_will_take_and_no_more(
        self, client: httpx.AsyncClient, db: AsyncSession, shop: dict[str, Product]
    ) -> None:
        """Ten of a product, twenty products: a cart past either would fail at checkout."""
        user = await make_user(db, email="exact@example.ge")
        line = {"productId": str(shop["cable"].id)}

        over_quantity = await client.put(
            CART, headers=auth_header(user), json={"items": [{**line, "qty": 11}]}
        )
        over_lines = await client.put(
            CART,
            headers=auth_header(user),
            json={"items": [{"productId": str(uuid.uuid4()), "qty": 1} for _ in range(21)]},
        )
        at_both = await client.put(
            CART, headers=auth_header(user), json={"items": [{**line, "qty": 10}]}
        )

        assert over_quantity.status_code == 400
        assert over_lines.status_code == 400
        assert at_both.status_code == 200

    async def test_an_empty_cart_is_allowed(
        self, client: httpx.AsyncClient, db: AsyncSession
    ) -> None:
        user = await make_user(db, email="empty@example.ge")

        response = await client.put(CART, headers=auth_header(user), json={"items": []})

        assert response.status_code == 200
        assert response.json()["items"] == []
