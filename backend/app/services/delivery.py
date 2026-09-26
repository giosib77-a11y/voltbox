"""What delivery costs, and where the shop delivers at all.

The one place these numbers live. The checkout computes the fee from here, and
GET /delivery hands the same table to the storefront - the cart, the checkout,
the header strip and the home page read it from there and keep no copy of their
own, so the price a customer is shown and the price they are charged cannot
disagree.

Set by the owner: Tbilisi 8 GEL, Rustavi 5 GEL, free from 50 GEL of goods. A
city is served when it is a key of `CITY_FEES` - adding one back is one line
here, and the checkout's city list follows it.

The fee is never read from the request, for the same reason a product price is
not: `CreateOrderRequest` forbids unknown fields, so a client that sends one is
refused rather than trusted.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.core.errors import ValidationError

#: Fee per city, in the order the checkout lists them. The keys are compared
#: with what the checkout sends, which is one of these strings.
CITY_FEES: dict[str, Decimal] = {
    "თბილისი": Decimal("8.00"),
    "რუსთავი": Decimal("5.00"),
}

#: Goods worth this much or more are delivered free - 50.00 itself included.
FREE_FROM = Decimal("50.00")


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


def fee_for(city: str, subtotal: Decimal) -> Decimal:
    """The delivery fee for goods worth `subtotal`, delivered to `city`."""
    fee = CITY_FEES[require_served(city)]
    if subtotal >= FREE_FROM:
        return _money(Decimal("0"))
    return _money(fee)
