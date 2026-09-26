"""The payment methods this shop offers, in the four places that name them.

There is no online payment here. Both methods mean "on delivery", so nothing in
this codebase moves money and no card detail is ever collected or stored - the
whole payment surface is one 32-character column with a CHECK on it.

What can still go wrong is drift. The list lives in four places, and each one
fails differently when it disagrees with the others:

  · app/schemas/order.py       - PAYMENT_METHODS is what an order may carry;
                                 OFFERED_PAYMENT_METHODS is what a new one may
                                 choose, and POST /orders refuses the rest
  · the orders.status CHECK    - lets the API accept what the database then
                                 rejects, which is a 500 on a valid checkout
  · src/constants/index.js     - the customer picks from a list that is missing
                                 an option, or sees "—" for their own choice
  · src/admin/statuses.jsx     - the operator packing the box reads
                                 `card_on_delivery` and has to guess

That last one is not hypothetical: the admin's detail page had a ternary on
'cash' and printed the raw value for the other method.

Card to the courier is no longer offered, so the two lists differ: a stored
order may still carry it and every page must still name it, but the checkout
must not show it, since the API would refuse the order.
"""

import re
from pathlib import Path
from typing import get_args

import pytest
from app.db.models import Order
from app.schemas.order import OFFERED_PAYMENT_METHODS, PAYMENT_METHODS, CreateOrderRequest
from sqlalchemy import CheckConstraint

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend" / "src"


def _js_methods(path: Path, name: str) -> set[str]:
    """The methods a JS declaration names.

    Two shapes, because the two sides chose differently: the shop keeps an
    array of `{value, label}` so it can be rendered in order, the admin keeps an
    object keyed by method so it can be looked up.
    """
    source = path.read_text(encoding="utf-8")
    start = source.index(f"export const {name}")
    end = min(
        index for index in (source.find("\n};", start), source.find("\n];", start)) if index != -1
    )
    body = source[start : end + 3]

    from_object = set(re.findall(r"^\s{2}([a-z_]+):", body, re.M))
    from_array = set(re.findall(r"value: '([a-z_]+)'", body))
    return from_object | from_array


def _js_offered(path: Path) -> set[str]:
    """The methods the checkout shows: the entries marked `offered: true`."""
    source = path.read_text(encoding="utf-8")
    start = source.index("export const PAYMENT_METHODS")
    body = source[start : source.index("\n];", start)]
    return set(re.findall(r"\{ value: '([a-z_]+)',[^}]*offered: true", body))


def test_the_schema_and_the_database_agree() -> None:
    """A method the API accepts and the column refuses is a 500 on checkout."""
    # The metadata naming convention prefixes the name given in the model, so
    # `payment_method_allowed` is stored as `ck_orders_payment_method_allowed`.
    # A mapped class's table is typed as the wider FromClause, which has no
    # constraints; the metadata hands back the Table itself.
    check = next(
        c
        for c in Order.metadata.tables[Order.__tablename__].constraints
        if isinstance(c, CheckConstraint)
        and isinstance(c.name, str)
        and "payment_method_allowed" in c.name
    )

    for method in PAYMENT_METHODS:
        assert f"'{method}'" in str(check.sqltext), method

    quoted = set(re.findall(r"'([a-z_]+)'", str(check.sqltext)))
    assert quoted == set(PAYMENT_METHODS)


@pytest.mark.parametrize("method", sorted(PAYMENT_METHODS))
def test_the_shop_can_offer_it(method: str) -> None:
    offered = _js_methods(FRONTEND / "constants" / "index.js", "PAYMENT_METHODS")

    assert method in offered, f"{method} is not in the list a customer picks from"


@pytest.mark.parametrize("method", sorted(PAYMENT_METHODS))
def test_the_operator_can_read_it(method: str) -> None:
    """Whoever is packing the box has to know what the courier collects."""
    labelled = _js_methods(FRONTEND / "admin" / "statuses.jsx", "PAYMENT_METHODS")

    assert method in labelled, f"{method} would be shown to an operator as a raw value"


def test_neither_side_offers_something_the_api_would_refuse() -> None:
    shop = _js_methods(FRONTEND / "constants" / "index.js", "PAYMENT_METHODS")
    admin = _js_methods(FRONTEND / "admin" / "statuses.jsx", "PAYMENT_METHODS")

    assert shop == set(PAYMENT_METHODS)
    assert admin == set(PAYMENT_METHODS)


def test_a_new_order_may_choose_only_what_is_offered() -> None:
    """The request's Literal is the list; OFFERED_PAYMENT_METHODS names it."""
    field = CreateOrderRequest.model_fields["payment_method"]

    assert set(get_args(field.annotation)) == set(OFFERED_PAYMENT_METHODS)
    assert set(OFFERED_PAYMENT_METHODS) <= set(PAYMENT_METHODS)
    assert "card_on_delivery" not in OFFERED_PAYMENT_METHODS


def test_the_checkout_shows_only_what_the_api_accepts() -> None:
    """An option the API refuses is a checkout that fails after the customer chose it."""
    assert _js_offered(FRONTEND / "constants" / "index.js") == set(OFFERED_PAYMENT_METHODS)


def test_the_extraction_found_something() -> None:
    """Guards the test: a renamed constant would make everything above pass."""
    assert len(PAYMENT_METHODS) == 2
    assert _js_offered(FRONTEND / "constants" / "index.js")
    assert _js_methods(FRONTEND / "constants" / "index.js", "PAYMENT_METHODS")
    assert _js_methods(FRONTEND / "admin" / "statuses.jsx", "PAYMENT_METHODS")
