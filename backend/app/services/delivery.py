"""What delivery costs, and where the shop delivers at all.

The one place these numbers live. The checkout computes the fee from here, and
GET /delivery hands the same table to the storefront - the cart, the checkout,
the header strip and the home page read it from there and keep no copy of their
own, so the price a customer is shown and the price they are charged cannot
disagree.

Set by the owner: Tbilisi 11 GEL, Rustavi 7 GEL, free from 100 GEL of goods, and
the courier takes a card in both cities. A city is served when it is a key of
`CITY_FEES` - adding one back is one line here, and the checkout's city list
follows it. Whether the courier takes a card there is `CARD_ON_DELIVERY_CITIES`,
read the same way by GET /delivery (what the checkout offers) and by POST
/orders (what it accepts).

The fee is never read from the request, for the same reason a product price is
not: `CreateOrderRequest` forbids unknown fields, so a client that sends one is
refused rather than trusted.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.core.errors import ValidationError

#: Fee per city, in the order the checkout lists them. The keys are compared
#: with what the checkout sends, which is one of these strings.
CITY_FEES: dict[str, Decimal] = {
    "თბილისი": Decimal("11.00"),
    "რუსთავი": Decimal("7.00"),
}

#: The cities where the courier carries a card terminal. A subset of the served
#: cities (a test pins that): a city outside CITY_FEES is refused as not served
#: before payment is even looked at. Removing a city here switches card off for
#: it alone; cash stays accepted everywhere the shop delivers.
CARD_ON_DELIVERY_CITIES: frozenset[str] = frozenset({"თბილისი", "რუსთავი"})

#: Goods worth this much or more are delivered free - 100.00 itself included.
FREE_FROM = Decimal("100.00")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def require_served(city: str) -> str:
    """`city` if the shop delivers there, else the 400 the checkout shows."""
    if city not in CITY_FEES:
        raise ValidationError(
            "Delivery is not available in this city",
            code="CITY_NOT_SERVED",
            details=[{"field": "customer.city", "cities": list(CITY_FEES)}],
        )
    return city


def require_payment_method(city: str, method: str) -> str:
    """`method` if an order to `city` may be paid that way, else the 400 the checkout shows.

    Only card on delivery depends on the city; cash is accepted wherever the
    shop delivers, and an unknown method never gets here (the request schema
    refuses it first).
    """
    if method == "card_on_delivery" and city not in CARD_ON_DELIVERY_CITIES:
        raise ValidationError(
            "Card payment on delivery is not available in this city",
            code="PAYMENT_METHOD_UNAVAILABLE",
            details=[{"field": "paymentMethod", "cities": sorted(CARD_ON_DELIVERY_CITIES)}],
        )
    return method


def fee_for(city: str, subtotal: Decimal) -> Decimal:
    """The delivery fee for goods worth `subtotal`, delivered to `city`."""
    fee = CITY_FEES[require_served(city)]
    if subtotal >= FREE_FROM:
        return _money(Decimal("0"))
    return _money(fee)
