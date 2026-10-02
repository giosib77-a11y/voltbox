"""შეკვეთების მარშრუტები."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, Request, status
from pydantic import ValidationError as BodyInvalid

from app.core.config import settings
from app.core.deps import CurrentUser, Db, OptionalUser
from app.core.errors import ValidationError
from app.core.rate_limit import LOOKUP_RATE_LIMIT, limiter
from app.db.models import Order, User
from app.schemas.order import (
    CreateOrderRequest,
    CustomerOut,
    OrderItemOut,
    OrderItemSnapshot,
    OrderLookupRequest,
    OrderOut,
    OrderTotals,
    PlacedOrderOut,
)
from app.services import order as order_service
from app.services import order_email, telegram

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
    response_model=PlacedOrderOut,
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
) -> PlacedOrderOut:
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
    # A replay gets a fresh one too - see issue_lookup_token.
    lookup_token = order_service.issue_lookup_token(order)
    await db.commit()
    await db.refresh(order)

    # A replay was announced the first time.
    if created:
        _announce(background, order, user)
    return PlacedOrderOut(**_to_out(order).model_dump(), lookup_token=lookup_token)


def _announce(background: BackgroundTasks, order: Order, user: User | None) -> None:
    """Tell the owner and the customer, after the commit and after the response.

    A background task runs once the response has been sent, so neither Telegram
    nor the email provider can fail this order or slow it down. What each
    message needs is copied out now, while the session is still open.
    """
    if settings.telegram_enabled:
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

    # A signed-in customer's address is their account's; a guest's is the
    # optional one typed at checkout. Without one there is no one to write to.
    recipient = user.email if user is not None else order.guest_email
    if settings.order_email_enabled and recipient:
        background.add_task(
            order_email.send_confirmation,
            order_email.OrderConfirmation(
                order_id=order.id,
                order_number=order.order_number,
                recipient=recipient,
                lines=tuple(
                    order_email.Line(
                        name=item.product_name,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        line_total=item.line_total,
                    )
                    for item in order.items
                ),
                subtotal=order.subtotal,
                shipping=order.shipping,
                total=order.total,
                currency=order.currency,
                city=str(order.shipping_address.get("city") or ""),
                address=str(order.shipping_address.get("address") or ""),
                payment_method=order.payment_method,
            ),
        )


@router.get("", summary="List the current user's orders", response_model=list[OrderOut])
async def list_orders(db: Db, user: CurrentUser) -> list[OrderOut]:
    return [_to_out(o) for o in await order_service.list_for_user(db, user.id)]


@router.post(
    "/lookup",
    summary="Find a guest order",
    description=(
        "For an order placed without an account: the order number and the "
        "`lookupToken` POST /orders returned with it, in the body - never in the "
        "URL, because a query string is written to every access log between "
        "here and the browser. A wrong token, an unknown order number and a "
        "body that is not a valid request all get the same 404: order numbers "
        "are sequential, so any difference would make them enumerable."
    ),
    response_model=OrderOut,
    # The body is read by hand (below), so FastAPI would not document it.
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": OrderLookupRequest.model_json_schema()}},
        }
    },
)
@limiter.limit(LOOKUP_RATE_LIMIT)
async def lookup_order(request: Request, db: Db) -> OrderOut:
    # Validated here and not by FastAPI, whose answer to a bad body is a 400
    # naming the field. That would tell a malformed request from a wrong token,
    # and the token from the order number. Nothing of the body is logged.
    try:
        payload = OrderLookupRequest.model_validate_json(await request.body())
    except BodyInvalid:
        raise order_service.order_not_found() from None
    order = await order_service.get_guest_order(db, payload.order_number, payload.token)
    return _to_out(order)


@router.get(
    "/{order_number}",
    summary="Get one of your own orders",
    description=(
        "Signed-in callers only. A guest uses POST /orders/lookup with the "
        "token issued at checkout — order numbers are guessable, so the "
        "number alone is never enough."
    ),
    response_model=OrderOut,
)
async def get_order(db: Db, user: CurrentUser, order_number: str) -> OrderOut:
    order = await order_service.get_by_number(db, order_number, user=user)
    return _to_out(order)
