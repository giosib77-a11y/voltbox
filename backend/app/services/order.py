"""შეკვეთების ბიზნეს-ლოგიკა — პროექტის ყველაზე მაღალი რისკის ზონა.

მთელი შექმნა ერთ ტრანზაქციაშია. თანმიმდევრობა და მიზეზები:

  1. პროდუქტების row-ები იბლოკება `FOR UPDATE`-ით, **id-ით დალაგებულად**.
     დალაგება აუცილებელია: ორი პარალელური შეკვეთა, რომლებიც ერთსა და იმავე ორ
     პროდუქტს სხვადასხვა რიგით ბლოკავს, ურთიერთბლოკირებას (deadlock) გამოიწვევს.
  2. ფასი *ყოველთვის* ბაზიდან მოდის. კლიენტის გამოგზავნილი ფასი არსად არ
     გამოიყენება — ეს ფასის გაყალბების ვექტორია.
  3. მარაგს მხოლოდ `services/inventory.adjust_stock` ცვლის — ის row-ს ბლოკავს,
     უარყოფით შედეგს კრძალავს და `inventory_movements`-ში ჩანაწერს წერს.
     ერთადერთი write-გზა იმიტომ, რომ ledger-ი სრული იყოს: სადმე დამალული
     UPDATE ისტორიაში ხვრელს ტოვებს, რომელიც თვეების მერე გამოჩნდება.
  4. სახელი, slug, სურათი და ფასი შეკვეთაში snapshot-ად ინახება: მოგვიანებით
     ფასის ცვლილება ისტორიას არ უნდა გადაწეროს.
"""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.limits import MAX_LINE_QUANTITY
from app.core.security import generate_order_lookup_token, hash_order_lookup_token
from app.db.models import (
    REASON_ORDER_PLACED,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    User,
)
from app.services import delivery, order_status
from app.services.contact import contact_matches, normalize_email, normalize_phone
from app.services.inventory import adjust_stock

MAX_QUANTITY = MAX_LINE_QUANTITY

#: The unique index that makes the key a claim rather than a hope. Named
#: explicitly because only *this* violation may be turned into a replay - any
#: other IntegrityError is a real fault and has to keep propagating.
IDEMPOTENCY_CONSTRAINT = "uq_orders_idempotency_key"


def money(value: Decimal) -> Decimal:
    """ფული ყოველთვის ორ ათწილადზე, ROUND_HALF_UP.

    Python-ის ნაგულისხმევი banker's rounding 2.5-ს 2-მდე ამრგვალებს — ფულში
    ეს ცენტების დაკარგვას ნიშნავს და frontend-ის Math.round-საც არ ემთხვევა.
    """
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def _next_order_number(db: AsyncSession) -> str:
    """`VB-YYYYMMDD-NNNNN` თანმიმდევრობიდან.

    random() + უნიკალურობის შემოწმების ციკლი რბოლის პირობებში ან დუბლიკატს
    იძლევა, ან უსასრულო ცდას — sequence ორივეს გამორიცხავს.

    Five digits, not four. The sequence is global and never reset, so the
    suffix is its value modulo the width, and a day's orders are consecutive
    values of it. With four digits the 10,001st order of a day came back to a
    number already issued that day; `uq_orders_order_number` refused it, and
    since `_is_idempotency_clash` rightly lets that violation through, checkout
    answered 500. What still holds: the same happens at the 100,001st.

    The date is the Tbilisi calendar day, not the database session's: the
    database runs in UTC, so a bare `now()` stamped an order placed between
    00:00 and 04:00 Tbilisi time with the previous day. What still holds: the
    sequence is global and never reset, so the suffix does not restart at 00001
    on a new day.
    """
    row = await db.execute(
        text(
            "SELECT to_char(now() AT TIME ZONE 'Asia/Tbilisi', 'YYYYMMDD') AS day, "
            "nextval('order_number_seq') AS seq"
        )
    )
    day, seq = row.one()
    return f"VB-{day}-{int(seq) % 100000:05d}"


async def _lock_products(db: AsyncSession, product_ids: list[UUID]) -> dict[UUID, Product]:
    """row-ების ბლოკირება, შემდეგ სრული ჩატვირთვა — ორ ნაბიჯად.

    ერთ ნაბიჯად არ გამოვა: `Product.brand` და `Product.category` `lazy="joined"`-ია,
    Postgres კი `FOR UPDATE`-ს outer join-ის nullable მხარეს არ უშვებს. ამიტომ ჯერ
    მინიმალურ SELECT-ს ვბლოკავთ, მერე იმავე ტრანზაქციაში სრულად ვტვირთავთ —
    row-ები უკვე ჩვენია.

    ⚠️ ORDER BY id — deadlock-ის თავიდან ასაცილებლად: ორმა პარალელურმა შეკვეთამ
    ერთი და იგივე პროდუქტები ერთი რიგით უნდა დაბლოკოს.
    """
    await db.execute(
        select(Product.id).where(Product.id.in_(product_ids)).order_by(Product.id).with_for_update()
    )
    stmt = (
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id.in_(product_ids))
        .order_by(Product.id)
    )
    products = (await db.scalars(stmt)).unique().all()
    return {product.id: product for product in products}


def owns_order(order: Order, *, user_id: UUID | None, customer: dict[str, Any]) -> bool:
    """Whether this requester is the person the stored order belongs to.

    An Idempotency-Key is a value a client chooses, so a repeat of one has to
    prove who it is before the order comes back. Without this check a guessed
    or copied key reads someone else's name, address and basket.

    An order placed while signed in belongs to that account and to nothing
    else - a guest who happens to know the email must not replay it.
    """
    if order.user_id is not None:
        return user_id is not None and order.user_id == user_id
    if user_id is not None:
        return False
    return contact_matches(
        customer.get("email"), email=order.guest_email, phone=order.guest_phone
    ) or contact_matches(customer.get("phone"), email=order.guest_email, phone=order.guest_phone)


def _merge_lines(items: list[tuple[UUID, int]]) -> dict[UUID, int]:
    """One quantity per product: a product sent on two lines is one line of the sum."""
    quantities: dict[UUID, int] = {}
    for product_id, qty in items:
        quantities[product_id] = quantities.get(product_id, 0) + qty
    return quantities


def request_hash(quantities: dict[UUID, int], customer: dict[str, Any], payment_method: str) -> str:
    """SHA-256 (hex) of the checkout as the shopper asked for it.

    Covers what makes one checkout a different purchase from another: the
    products and their quantities, the customer's details and the payment
    method. It does not cover the account (`owns_order` answers who is asking),
    the Idempotency-Key itself, or anything the server computes (prices, totals).

    Deterministic: the same logical request always gives the same hash.
      - items are the merged quantities, ordered by product id, so line order
        and a product split over two lines make no difference;
      - the customer is taken as the schema validated it (whitespace already
        trimmed), except that the email and the phone are normalised the way
        `owns_order` compares them - `Giorgi@Example.GE` and `giorgi@example.ge`
        are one person and a retry that differs only so still replays.
        Absent and empty email are the same (`exclude_none` drops the former,
        the blank-email validator turns the latter into None).

    What still holds: any other change to the customer - name, address, city,
    comment - is a different request. Orders placed before migration 0017 carry
    no hash and are compared on the key alone.
    """
    contact = {
        **customer,
        "email": normalize_email(customer.get("email")),
        "phone": normalize_phone(customer.get("phone")),
    }
    canonical = {
        "items": [[str(product_id), quantities[product_id]] for product_id in sorted(quantities)],
        "customer": {key: value for key, value in contact.items() if value is not None},
        "paymentMethod": payment_method,
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _replay(order: Order, *, user_id: UUID | None, customer: dict[str, Any], digest: str) -> Order:
    """Return the stored order to its owner, or refuse without describing it.

    The owner check comes first: a requester who does not own the order is told
    only that the key is taken, whatever they sent, so a different hash cannot
    be used to probe what the stored order contained.
    """
    if not owns_order(order, user_id=user_id, customer=customer):
        raise ConflictError(
            "This idempotency key belongs to a different order",
            code="IDEMPOTENCY_KEY_CONFLICT",
        )
    # NULL: placed before migration 0017, nothing to compare - replay as before.
    if order.request_hash is not None and order.request_hash != digest:
        raise ConflictError(
            "This idempotency key was already used for a different request",
            code="IDEMPOTENCY_KEY_REUSED",
        )
    return order


async def _claim_key(
    db: AsyncSession,
    *,
    idempotency_key: str | None,
    customer: dict[str, Any],
    payment_method: str,
    user: User | None,
    digest: str,
) -> Order:
    """Insert the order row, taking the key before anything else can fail.

    The claim has to happen first, not last. Two things go wrong otherwise:

      · A duplicate submitted while the first request is still running races to
        the same INSERT and one of them dies on the unique index - a 500 on a
        checkout the shopper already completed.
      · On the last unit in stock the duplicate reaches the stock check before
        the original has committed, and the shopper is told the item ran out
        instead of being shown the order they just placed.

    With the row inserted up front, a concurrent duplicate blocks on the unique
    index until the original commits and then sees it, which is the answer it
    wanted. Totals are filled in once the prices are known - the row is only
    visible inside this transaction until then.
    """
    order = Order(
        order_number=await _next_order_number(db),
        user_id=user.id if user else None,
        guest_email=customer.get("email") if user is None else None,
        guest_phone=customer.get("phone") if user is None else None,
        status="pending",
        customer=customer,
        shipping_address={
            "city": customer.get("city"),
            "address": customer.get("address"),
            "phone": customer.get("phone"),
        },
        subtotal=Decimal("0"),
        shipping=Decimal("0"),
        total=Decimal("0"),
        currency=settings.currency,
        payment_method=payment_method,
        notes=customer.get("comment") or None,
        idempotency_key=idempotency_key,
        request_hash=digest,
    )
    db.add(order)
    await db.flush()
    return order


def _is_idempotency_clash(error: IntegrityError) -> bool:
    """Only the idempotency key's own unique violation, never anything else.

    A blanket `except IntegrityError` here would swallow a duplicate order
    number, a broken foreign key or a violated check constraint and answer with
    somebody else's order.
    """
    return IDEMPOTENCY_CONSTRAINT in str(getattr(error, "orig", error))


async def create_order(
    db: AsyncSession,
    *,
    items: list[tuple[UUID, int]],
    customer: dict[str, Any],
    payment_method: str,
    user: User | None,
    idempotency_key: str | None = None,
) -> Order:
    """შეკვეთის შექმნა ერთ ტრანზაქციაში.

    `items` მხოლოდ (productId, qty) წყვილებია — ფასი კლიენტისგან არ მოდის.
    """
    order, _ = await place_order(
        db,
        items=items,
        customer=customer,
        payment_method=payment_method,
        user=user,
        idempotency_key=idempotency_key,
    )
    return order


async def place_order(
    db: AsyncSession,
    *,
    items: list[tuple[UUID, int]],
    customer: dict[str, Any],
    payment_method: str,
    user: User | None,
    idempotency_key: str | None = None,
) -> tuple[Order, bool]:
    """`create_order`, plus whether this call placed the order.

    False means a replay: the order already existed under this Idempotency-Key.
    The route needs to know, so that a double-submitted checkout does not tell
    the owner about the same order twice.
    """
    # The id, taken now. The clash path below rolls the session back, which
    # expires `user`, and reading an expired attribute goes back to the database
    # - from async code that is MissingGreenlet, a 500 for an order that exists.
    user_id = user.id if user is not None else None

    # ერთი პროდუქტი ორჯერ: რაოდენობებს ვაჯამებთ, თორემ FOR UPDATE-ის შემდეგ
    # ორივე ხაზი ერთსა და იმავე მარაგს დაუპირისპირდებოდა
    quantities = _merge_lines(items)
    digest = request_hash(quantities, customer, payment_method)

    if idempotency_key:
        # Deliberately not filtered by `deleted_at`: an order in the admin trash
        # still holds its key, and a retry of its checkout has to be answered
        # with that order. Hiding it here would place a second order and take
        # the stock a second time. What still holds: every other reader in this
        # module skips the trash.
        existing = await db.scalar(select(Order).where(Order.idempotency_key == idempotency_key))
        if existing is not None:
            # ორმაგად გაგზავნილი checkout — იმავე შეკვეთას ვაბრუნებთ და მეორეს
            # არ ვქმნით. მფლობელობა აუცილებლად მოწმდება: გასაღები კლიენტის
            # არჩეულია და გამოცნობილით სხვისი შეკვეთა იკითხებოდა.
            return _replay(existing, user_id=user_id, customer=customer, digest=digest), False

    for product_id, qty in quantities.items():
        if qty > MAX_QUANTITY:
            raise ValidationError(
                f"Quantity must not exceed {MAX_QUANTITY}",
                code="INVALID_QUANTITY",
                details=[{"field": "items", "productId": str(product_id), "max": MAX_QUANTITY}],
            )

    # Before the key is claimed: a city the shop does not deliver to is the
    # customer's mistake to correct, not an order to half-create and roll back.
    delivery.require_served(str(customer.get("city", "")))

    # The key is claimed here, before any check that can fail or block. A
    # duplicate arriving now waits on the unique index instead of racing us to
    # an IntegrityError or being told the last unit is gone.
    try:
        order = await _claim_key(
            db,
            idempotency_key=idempotency_key,
            customer=customer,
            payment_method=payment_method,
            user=user,
            digest=digest,
        )
    except IntegrityError as error:
        if not _is_idempotency_clash(error):
            raise
        # The original committed while we waited. Start a clean transaction,
        # read what it wrote, and hand it back to whoever owns it. Unfiltered
        # by `deleted_at` for the same reason as the first lookup: the original
        # may have been trashed in the meantime.
        await db.rollback()
        existing = await db.scalar(select(Order).where(Order.idempotency_key == idempotency_key))
        if existing is None:  # pragma: no cover - the violation proves it exists
            raise
        return _replay(existing, user_id=user_id, customer=customer, digest=digest), False

    products = await _lock_products(db, sorted(quantities))

    order_items: list[OrderItem] = []
    subtotal = Decimal("0")

    for product_id in sorted(quantities):
        qty = quantities[product_id]
        product = products.get(product_id)
        # Archiving also clears is_active, so the first condition already covers
        # it; archived_at is checked too so the rule survives if that ever
        # changes. A product can be retired while it sits in someone's cart.
        if product is None or not product.is_active or product.archived_at is not None:
            raise NotFoundError(
                "Product not found",
                code="PRODUCT_NOT_FOUND",
                details={"productId": str(product_id)},
            )
        if product.stock < qty:
            raise ConflictError(
                "Not enough stock",
                code="INSUFFICIENT_STOCK",
                details={
                    "productId": str(product_id),
                    "requested": qty,
                    "available": product.stock,
                },
            )

        unit_price = money(product.price)
        line_total = money(unit_price * qty)
        subtotal += line_total

        # is_primary first, then position - the two can disagree. The primary
        # image is the one the product page shows, and it is a partial unique
        # index rather than a rule about ordering, so a shop that reorders
        # images without touching the primary would have snapshotted a
        # different photo into the order than the customer was looking at.
        # And a snapshot is forever: the order keeps whatever went in.
        primary = next(
            (
                image.url
                for image in sorted(product.images, key=lambda i: (not i.is_primary, i.position))
            ),
            "",
        )
        order_items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                product_slug=product.slug,
                image_url=primary,
                unit_price=unit_price,
                quantity=qty,
                line_total=line_total,
            )
        )

    subtotal = money(subtotal)
    # From the city and the goods alone. Nothing the client sent is read here.
    shipping = delivery.fee_for(str(customer.get("city", "")), subtotal)

    order.subtotal = subtotal
    order.shipping = shipping
    order.total = money(subtotal + shipping)

    # `order.items = [...]` would have to read the collection as it stands to
    # work out the difference, and the row was flushed a moment ago with the
    # collection never loaded - that read is lazy IO inside async code, which
    # raises MissingGreenlet. Adding the rows against the id we already have
    # avoids the question; the refresh then loads them back explicitly.
    for item in order_items:
        item.order_id = order.id
    db.add_all(order_items)
    # The timeline's first line, as migration 0004 wrote one for every order that
    # existed before it: from_status is NOT NULL, so "placed" is pending -> pending.
    db.add(OrderStatusHistory(order_id=order.id, from_status="pending", to_status="pending"))
    await db.flush()
    await db.refresh(order, ["items"])

    # მარაგი ერთადერთი გზით იცვლება — `inventory.adjust_stock`-ით: ის row-ს
    # ბლოკავს, უარყოფით შედეგზე 409-ს აგდებს და ledger-ში ჩანაწერს წერს.
    # თანმიმდევრობა კვლავ id-ით დალაგებულია — ორმა პარალელურმა შეკვეთამ ერთი
    # და იგივე პროდუქტები ერთი რიგით უნდა დაბლოკოს, თორემ deadlock.
    for product_id in sorted(quantities):
        await adjust_stock(
            db,
            product_id,
            -quantities[product_id],
            REASON_ORDER_PLACED,
            order_id=order.id,
        )

    return order, True


async def list_for_user(db: AsyncSession, user_id: UUID) -> list[Order]:
    # A trashed order is the shop's to keep or purge, not part of the customer's
    # history (PROJECT.md -> Business Rules -> Order trash).
    stmt = (
        select(Order)
        .where(Order.user_id == user_id, Order.deleted_at.is_(None))
        .order_by(Order.created_at.desc())
        .limit(100)
    )
    return list((await db.scalars(stmt)).unique().all())


async def get_by_number(db: AsyncSession, order_number: str, *, user: User) -> Order:
    """შეკვეთის წაკითხვა ნომრით — მხოლოდ საკუთარი, ავტორიზებულისთვის.

    შეკვეთის ნომერი თანმიმდევრობითია და გამოცნობადი, ამიტომ მარტო ნომრით
    წვდომა დაუშვებელია. სხვისი შეკვეთა 404-ია და არა 403. A guest reads theirs
    with `get_guest_order`.

    A trashed order is a 404 as well, the same one: to the customer it no
    longer exists, and a different answer would tell them it does.
    """
    order = await db.scalar(
        select(Order).where(Order.order_number == order_number, Order.deleted_at.is_(None))
    )
    if order is None or order.user_id != user.id:
        raise order_not_found()
    return order


def order_not_found() -> NotFoundError:
    """The one refusal of a lookup, whatever went wrong.

    Order numbers are sequential, so an answer that told "no such order" from
    "not yours" would turn them into a list of real orders.
    """
    return NotFoundError("Order not found", code="ORDER_NOT_FOUND")


def issue_lookup_token(order: Order) -> str | None:
    """Give a guest order a new lookup token; return the raw one, or None.

    Only the hash is kept, so the raw token exists once - in this response - and
    the caller has to commit for it to work. A signed-in customer's order gets
    none: it is read through the account.

    Called on a replayed checkout too, which replaces the token. The replay is
    a retry whose first answer never arrived, so the browser holds no token
    yet, and the stored hash cannot be turned back into one. Whoever replays
    has already proved more than a token would: the Idempotency-Key, a UUID
    that never left their browser, and the contact (`owns_order`).
    """
    if order.user_id is not None:
        return None
    raw, order.lookup_token_hash = generate_order_lookup_token()
    return raw


async def get_guest_order(db: AsyncSession, order_number: str, token: str) -> Order:
    """A guest order, for the holder of the token it was issued with.

    One query for both conditions, so an unknown number and a wrong token run
    the same statement and fail at the same place. The phone is no part of it:
    a phone number is known to the shopper's friends, family and every shop
    they have given it to, and the order number is a counter.

    A trashed order is one more reason for the same refusal, inside the same
    statement: the holder of a right token must not learn that the order exists
    but was deleted.
    """
    order = await db.scalar(
        select(Order).where(
            Order.order_number == order_number,
            Order.lookup_token_hash == hash_order_lookup_token(token),
            Order.deleted_at.is_(None),
        )
    )
    if order is None:
        raise order_not_found()
    return order


async def cancel(db: AsyncSession, order: Order, *, actor_id: UUID | None = None) -> Order:
    """გაუქმება მარაგს აბრუნებს — სხვაგვარად ჩამოწერილი ერთეულები დაიკარგება.

    Delegates to the state machine rather than repeating it. This used to hold
    its own copy of the locking, the restock loop and the "can it still be
    cancelled?" rule, and moved the order to `cancelled` while writing no
    history row - so an order cancelled through this door sat in the panel with
    no record of when it happened or who did it. Two implementations of one
    transition also drift: the graph in order_status.py is the one the admin API
    and the UI already read.

    What is kept is the refusal's code. `ORDER_NOT_CANCELLABLE` is the one a
    customer is meant to read - the frontend already has the sentence for it -
    while `INVALID_TRANSITION` names a move in a graph they never see.
    `ORDER_IN_TRASH` is not that kind of refusal - the move is allowed, the
    order is frozen in the admin trash - so it passes through unchanged rather
    than being reported as an order that can no longer be cancelled.
    """
    try:
        return await order_status.transition(db, order.id, "cancelled", actor_id=actor_id)
    except ConflictError as exc:
        if exc.code == "ORDER_IN_TRASH":
            raise
        raise ConflictError(
            "Order can no longer be cancelled", code="ORDER_NOT_CANCELLABLE"
        ) from exc
