"""შეკვეთების მარშრუტები."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, Request, status

from app.core.config import settings
from app.core.deps import CurrentUser, Db, OptionalUser
from app.core.errors import ValidationError
from app.core.rate_limit import LOOKUP_RATE_LIMIT, limiter
from app.db.models import Order
from app.schemas.order import (
    CreateOrderRequest,
    CustomerOut,
    OrderItemOut,
    OrderItemSnapshot,
    OrderLookupRequest,
    OrderOut,
    OrderTotals,
)
from app.services import order as order_service
from app.services import telegram

router = APIRouter(prefix="/orders", tags=["orders"])


def _required_key(raw: str | None) -> str:
    """An Idempotency-Key is required, and must be a UUID.

    Without a key the column is NULL, and Postgres counts every NULL as
    distinct, so the UNIQUE index lets a retry straight through: _lock_products
    and adjust_stock run a second time, the stock is decremented twice, and the
    customer owes for two orders that the admin sees as two. The header is the
    only thing between a double-tapped "confirm" and that duplicate, so an
    absent one is refused rather than quietly treated as "no replay wanted".

    The key is a permanent claim on a row - once taken, that value can never
    produce a different order. Accepting free text would let a client take
    "checkout" and then wonder why every later order replays the first one.
    """
    candidate = (raw or "").strip()
    if not candidate:
        raise ValidationError(
            "Idempotency-Key header is required, and must be a UUID",
            code="IDEMPOTENCY_KEY_REQUIRED",
            details=[{"field": "Idempotency-Key"}],
        )
    try:
        uuid.UUID(candidate)
    except ValueError:
        raise ValidationError(
            "Idempotency-Key must be a UUID",
            code="INVALID_IDEMPOTENCY_KEY",
            details=[{"field": "Idempotency-Key"}],
        ) from None
    return candidate


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
        "any price sent by the client is rejected. An Idempotency-Key header "
        "holding a UUID is **required**: it is what makes a double-submitted "
        "checkout return the original order instead of placing a second one."
    ),
    status_code=status.HTTP_201_CREATED,
    response_model=OrderOut,
)
async def create_order(
    db: Db,
    user: OptionalUser,
    payload: CreateOrderRequest,
    background: BackgroundTasks,
    # The header is required, but it is declared optional here on purpose: a
    # parameter FastAPI itself marks required fails in its own validator, and
    # that answer is the generic VALIDATION_ERROR / "Field required", which
    # names neither the header nor the UUID it has to hold. _required_key
    # raises instead, so a caller that forgot it is told what to send.
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", description="Required. A UUID identifying this checkout."),
    ] = None,
) -> OrderOut:
    # ქართული ახსნა: მთელი ლოგიკა სერვისშია ერთ ტრანზაქციაში — router მხოლოდ
    # (productId, qty) წყვილებს გადასცემს. ფასი კლიენტისგან არსად არ მოდის.
    order, created = await order_service.place_order(
        db,
        items=[(item.product_id, item.qty) for item in payload.items],
        customer=payload.customer.model_dump(exclude_none=True),
        payment_method=payload.payment_method,
        user=user,
        idempotency_key=_required_key(idempotency_key),
    )
    await db.commit()
    await db.refresh(order)

    # After the commit and after the response: a background task runs once the
    # response has been sent, so Telegram can neither fail this order nor slow
    # it down. A replay was announced the first time.
    if created and settings.telegram_enabled:
        background.add_task(
            telegram.notify_order_placed,
            telegram.OrderNotice(
                order_id=order.id,
                order_number=order.order_number,
                subtotal=order.subtotal,
                shipping=order.shipping,
                total=order.total,
                currency=order.currency,
                item_count=sum(item.quantity for item in order.items),
            ),
        )
    return _to_out(order)


@router.get("", summary="List the current user's orders", response_model=list[OrderOut])
async def list_orders(db: Db, user: CurrentUser) -> list[OrderOut]:
    return [_to_out(o) for o in await order_service.list_for_user(db, user.id)]


@router.post(
    "/lookup",
    summary="Find a guest order",
    description=(
        "For an order placed without an account. The email or phone used at "
        "checkout goes in the body, never in the URL, because a query string "
        "is written to every access log between here and the browser. "
        "An unknown order number and a contact that does not match give the "
        "same 404: order numbers are sequential, so a different answer would "
        "make them enumerable."
    ),
    response_model=OrderOut,
)
@limiter.limit(LOOKUP_RATE_LIMIT)
async def lookup_order(
    request: Request, db: Db, user: OptionalUser, payload: OrderLookupRequest
) -> OrderOut:
    # `request` is what slowapi reads the client address from. Unused here.
    order = await order_service.get_by_number(
        db, payload.order_number, user=user, contact=payload.contact
    )
    return _to_out(order)


@router.get(
    "/{order_number}",
    summary="Get one of your own orders",
    description=(
        "Signed-in callers only. A guest uses POST /orders/lookup — order "
        "numbers are guessable, so the number alone is never enough."
    ),
    response_model=OrderOut,
)
async def get_order(db: Db, user: CurrentUser, order_number: str) -> OrderOut:
    order = await order_service.get_by_number(db, order_number, user=user)
    return _to_out(order)
