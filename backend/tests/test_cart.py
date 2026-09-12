"""The saved cart.

What it covers: that a signed-in cart follows the person between devices, that
prices come from the catalogue rather than from whatever the client sent, and
that signing in with a basket already in the browser does not double an order.

The merge rule is the part worth pinning. Taking the larger quantity rather than
the sum is a judgement - two cables added on a phone and two on a laptop is one
person meaning two - and summing would be the kind of change that looks harmless
in review and charges somebody twice.
"""

import httpx
import pytest
from app.db.models import Cart, Product
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

CART = "/api/v1/cart"


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

        from datetime import UTC, datetime

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
        import uuid

        user = await make_user(db, email="hoarder@example.ge")

        response = await client.put(
            CART,
            headers=auth_header(user),
            json={"items": [{"productId": str(uuid.uuid4()), "qty": 1} for _ in range(51)]},
        )

        assert response.status_code == 400

    async def test_an_empty_cart_is_allowed(
        self, client: httpx.AsyncClient, db: AsyncSession
    ) -> None:
        user = await make_user(db, email="empty@example.ge")

        response = await client.put(CART, headers=auth_header(user), json={"items": []})

        assert response.status_code == 200
        assert response.json()["items"] == []
