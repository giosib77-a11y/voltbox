"""მიწოდების წესები — ქალაქები, ტარიფები და უფასო მიწოდების ზღვარი."""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.order import DeliveryCityOut, DeliveryRulesOut
from app.services import delivery

router = APIRouter(tags=["orders"])


@router.get(
    "/delivery",
    summary="Delivery rules",
    description=(
        "The cities the shop delivers to, the fee for each, and the goods total "
        "from which delivery is free. The storefront renders its prices from this "
        "and keeps no copy; POST /orders computes the fee from the same table."
    ),
    response_model=DeliveryRulesOut,
)
async def delivery_rules() -> DeliveryRulesOut:
    return DeliveryRulesOut(
        cities=[DeliveryCityOut(name=name, fee=fee) for name, fee in delivery.CITY_FEES.items()],
        free_from=delivery.FREE_FROM,
        currency=settings.currency,
    )
