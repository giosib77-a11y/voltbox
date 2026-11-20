"""Which cities the courier takes a card in: the table, the check and GET /delivery.

The table is `delivery.CARD_ON_DELIVERY_CITIES`. POST /orders enforces it
(tests/test_orders.py::TestPaymentMethod); GET /delivery tells the checkout
which cities to offer card for, so the two cannot disagree.
"""

import re
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from app.core.errors import ValidationError
from app.services import delivery

MOCK_RULES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "data" / "delivery.js"
_MOCK_CITY = re.compile(
    r"\{\s*name:\s*'([^']+)'\s*,\s*fee:\s*(\d+(?:\.\d+)?)\s*,\s*cardOnDelivery:\s*(true|false)\s*\}"
)
_MOCK_FREE_FROM = re.compile(r"freeFrom:\s*(\d+(?:\.\d+)?)")


def test_the_mock_mode_rules_equal_the_servers() -> None:
    """frontend/src/data/delivery.js is mock mode's fake GET /delivery; it went stale once."""
    text = MOCK_RULES.read_text(encoding="utf-8")
    cities = _MOCK_CITY.findall(text)
    free_from = _MOCK_FREE_FROM.findall(text)

    assert [name for name, _, _ in cities] == list(delivery.CITY_FEES)
    assert [Decimal(fee) for _, fee, _ in cities] == list(delivery.CITY_FEES.values())
    assert {name for name, _, card in cities if card == "true"} == delivery.CARD_ON_DELIVERY_CITIES
    assert [Decimal(value) for value in free_from] == [delivery.FREE_FROM]


def test_every_card_city_is_a_served_city() -> None:
    """A card city outside CITY_FEES would be offered a method for a city the shop refuses."""
    assert set(delivery.CITY_FEES) >= delivery.CARD_ON_DELIVERY_CITIES
    assert {"თბილისი", "რუსთავი"} == delivery.CARD_ON_DELIVERY_CITIES


def test_the_free_delivery_threshold_is_one_hundred() -> None:
    assert Decimal("100.00") == delivery.FREE_FROM


@pytest.mark.parametrize("city", sorted(delivery.CITY_FEES))
def test_cash_is_accepted_in_every_served_city(monkeypatch: pytest.MonkeyPatch, city: str) -> None:
    # Even with no card city at all, cash is not touched.
    monkeypatch.setattr(delivery, "CARD_ON_DELIVERY_CITIES", frozenset())

    assert delivery.require_payment_method(city, "cash") == "cash"


def test_card_is_accepted_in_a_card_city() -> None:
    assert delivery.require_payment_method("რუსთავი", "card_on_delivery") == "card_on_delivery"


def test_card_elsewhere_is_a_400_with_a_code_and_the_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(delivery, "CARD_ON_DELIVERY_CITIES", frozenset({"თბილისი"}))

    with pytest.raises(ValidationError) as raised:
        delivery.require_payment_method("რუსთავი", "card_on_delivery")

    assert raised.value.code == "PAYMENT_METHOD_UNAVAILABLE"
    assert raised.value.details == [{"field": "paymentMethod", "cities": ["თბილისი"]}]


async def test_the_storefront_is_told_per_city(
    monkeypatch: pytest.MonkeyPatch, client: httpx.AsyncClient
) -> None:
    monkeypatch.setattr(delivery, "CARD_ON_DELIVERY_CITIES", frozenset({"თბილისი"}))

    response = await client.get("/api/v1/delivery")

    assert response.status_code == 200
    assert {c["name"]: c["cardOnDelivery"] for c in response.json()["cities"]} == {
        "თბილისი": True,
        "რუსთავი": False,
    }
