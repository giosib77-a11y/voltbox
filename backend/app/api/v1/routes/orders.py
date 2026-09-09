"""შეკვეთების მარშრუტები."""

from typing import Annotated

from fastapi import APIRouter, Header, Query, status

from app.core.deps import CurrentUser, Db, OptionalUser
from app.db.models import Order
from app.schemas.order import (
    CreateOrderRequest,
    CustomerOut,
    OrderItemOut,
    OrderItemSnapshot,
    OrderOut,
    OrderTotals,
)
from app.services import order as order_service

router = APIRouter(prefix="/orders", tags=["orders"])


def _to_out(order: Order) -> OrderOut:
    return OrderOut(
        order_number=order.order_number,
        created_at=order.created_at,
        status=order.status,
        payment_method=order.payment_method,
        currency=order.currency,
        customer=CustomerOut.model_validate(order.customer),
        totals=OrderTotals(subtotal=order.subtotal, shipping=order.shipping, total=order.total),
        items=[
            OrderItemOut(
                product_id=item.product_id,
                qty=item.quantity,
                snapshot=OrderItemSnapshot(
                    name=item.product_name,
                    slug=item.product_slug,
                    image=item.image_url,
                    price=item.unit_price,
                ),
            )
            for item in order.items
        ],
    )


@router.post(
    "",
    summary="Create an order",
    description=(
        "Guest checkout is allowed. Prices are always taken from the database; "
        "any price sent by the client is rejected. Send an Idempotency-Key header "
        "to make a double-submitted checkout return the original order."
    ),
    status_code=status.HTTP_201_CREATED,
    response_model=OrderOut,
)
async def create_order(
    db: Db,
    user: OptionalUser,
    payload: CreateOrderRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderOut:
    # ქართული ახსნა: მთელი ლოგიკა სერვისშია ერთ ტრანზაქციაში — router მხოლოდ
    # (productId, qty) წყვილებს გადასცემს. ფასი კლიენტისგან არსად არ მოდის.
    order = await order_service.create_order(
        db,
        items=[(item.product_id, item.qty) for item in payload.items],
        customer=payload.customer.model_dump(exclude_none=True),
        payment_method=payload.payment_method,
        user=user,
        idempotency_key=idempotency_key,
    )
    await db.commit()
    await db.refresh(order)
    return _to_out(order)


@router.get("", summary="List the current user's orders", response_model=list[OrderOut])
async def list_orders(db: Db, user: CurrentUser) -> list[OrderOut]:
    return [_to_out(o) for o in await order_service.list_for_user(db, user.id)]


@router.get(
    "/{order_number}",
    summary="Get an order by number",
    description=(
        "Authenticated users can read their own orders. Guests must supply the "
        "email or phone used at checkout — order numbers are guessable."
    ),
    response_model=OrderOut,
)
async def get_order(
    db: Db,
    user: OptionalUser,
    order_number: str,
    email: Annotated[str | None, Query(description="Contact used at checkout")] = None,
) -> OrderOut:
    order = await order_service.get_by_number(db, order_number, user=user, email=email)
    return _to_out(order)
