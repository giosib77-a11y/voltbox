"""კალათის მარშრუტები — მხოლოდ ავტორიზებულებისთვის.

A guest has no account to hang a cart on, so theirs stays in the browser and
these routes simply do not apply to them. For everyone else the browser is
still where shopping happens - every `+` and `-` is local and instant - and
this is the copy that survives a different device or a cleared browser.

`PUT` replaces, `POST /merge` folds in. The difference matters exactly once: at
sign-in, when the person may have a basket in this browser *and* one saved from
somewhere else, and replacing would throw one of them away without asking.
"""

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, Db
from app.schemas.cart import CartOut, CartRequest
from app.services import cart as cart_service

router = APIRouter(prefix="/cart", tags=["cart"])


def _payload(items: CartRequest) -> list[dict[str, object]]:
    return [{"productId": str(line.product_id), "qty": line.qty} for line in items.items]


@router.get(
    "",
    summary="The saved cart",
    description=(
        "Lines are priced from the catalogue as it is now, not as it was when "
        "they were saved. A product that has since been archived or deleted is "
        "absent rather than an error."
    ),
    response_model=CartOut,
)
async def read_cart(db: Db, user: CurrentUser) -> CartOut:
    return CartOut(items=await cart_service.get_cart(db, user.id))


@router.put(
    "",
    summary="Replace the saved cart",
    description="The browser is the source of truth while shopping; this stores what it holds.",
    response_model=CartOut,
)
async def replace_cart(db: Db, user: CurrentUser, payload: CartRequest) -> CartOut:
    items = await cart_service.save_cart(db, user.id, _payload(payload))
    await db.commit()
    return CartOut(items=items)


@router.post(
    "/merge",
    summary="Fold this browser's cart into the saved one",
    description=(
        "For signing in. Where both carts hold the same product the larger "
        "quantity wins rather than the sum: two added here and two there is one "
        "person meaning two, and summing would double an order quietly."
    ),
    response_model=CartOut,
)
async def merge_cart(db: Db, user: CurrentUser, payload: CartRequest) -> CartOut:
    items = await cart_service.merge_cart(db, user.id, _payload(payload))
    await db.commit()
    return CartOut(items=items)


@router.delete("", summary="Empty the saved cart", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(db: Db, user: CurrentUser) -> None:
    await cart_service.clear_cart(db, user.id)
    await db.commit()
