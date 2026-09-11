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

from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import (
    REASON_ORDER_CANCELLED,
    REASON_ORDER_PLACED,
    Order,
    OrderItem,
    Product,
    User,
)
from app.services.contact import contact_matches
from app.services.inventory import adjust_stock

MAX_QUANTITY = 99

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


def calc_shipping(subtotal: Decimal) -> Decimal:
    """ზღვარი და ტარიფი კონფიგიდან — frontend-ის SHIPPING-ს უნდა ემთხვეოდეს."""
    if subtotal <= 0:
        return money(Decimal("0"))
    if subtotal >= Decimal(settings.shipping_free_threshold):
        return money(Decimal("0"))
    return money(Decimal(settings.shipping_flat_fee))


async def _next_order_number(db: AsyncSession) -> str:
    """`VB-YYYYMMDD-NNNN` თანმიმდევრობიდან.

    random() + უნიკალურობის შემოწმების ციკლი რბოლის პირობებში ან დუბლიკატს
    იძლევა, ან უსასრულო ცდას — sequence ორივეს გამორიცხავს.
    """
    row = await db.execute(
        text("SELECT to_char(now(), 'YYYYMMDD') AS day, nextval('order_number_seq') AS seq")
    )
    day, seq = row.one()
    return f"VB-{day}-{int(seq) % 10000:04d}"


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


def owns_order(order: Order, *, user: User | None, customer: dict[str, Any]) -> bool:
    """Whether this requester is the person the stored order belongs to.

    An Idempotency-Key is a value a client chooses, so a repeat of one has to
    prove who it is before the order comes back. Without this check a guessed
    or copied key reads someone else's name, address and basket.

    An order placed while signed in belongs to that account and to nothing
    else - a guest who happens to know the email must not replay it.
    """
    if order.user_id is not None:
        return user is not None and order.user_id == user.id
    if user is not None:
        return False
    return contact_matches(
        customer.get("email"), email=order.guest_email, phone=order.guest_phone
    ) or contact_matches(customer.get("phone"), email=order.guest_email, phone=order.guest_phone)


def _replay(order: Order, *, user: User | None, customer: dict[str, Any]) -> Order:
    """Return the stored order to its owner, or refuse without describing it."""
    if owns_order(order, user=user, customer=customer):
        return order
    raise ConflictError(
        "This idempotency key belongs to a different order",
        code="IDEMPOTENCY_KEY_CONFLICT",
    )


async def _claim_key(
    db: AsyncSession,
    *,
    idempotency_key: str | None,
    customer: dict[str, Any],
    payment_method: str,
    user: User | None,
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
    if idempotency_key:
        existing = await db.scalar(select(Order).where(Order.idempotency_key == idempotency_key))
        if existing is not None:
            # ორმაგად გაგზავნილი checkout — იმავე შეკვეთას ვაბრუნებთ და მეორეს
            # არ ვქმნით. მფლობელობა აუცილებლად მოწმდება: გასაღები კლიენტის
            # არჩეულია და გამოცნობილით სხვისი შეკვეთა იკითხებოდა.
            return _replay(existing, user=user, customer=customer)

    # ერთი პროდუქტი ორჯერ: რაოდენობებს ვაჯამებთ, თორემ FOR UPDATE-ის შემდეგ
    # ორივე ხაზი ერთსა და იმავე მარაგს დაუპირისპირდებოდა
    quantities: dict[UUID, int] = {}
    for product_id, qty in items:
        quantities[product_id] = quantities.get(product_id, 0) + qty

    for product_id, qty in quantities.items():
        if qty > MAX_QUANTITY:
            raise ValidationError(
                f"Quantity must not exceed {MAX_QUANTITY}",
                code="INVALID_QUANTITY",
                details=[{"field": "items", "productId": str(product_id), "max": MAX_QUANTITY}],
            )

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
        )
    except IntegrityError as error:
        if not _is_idempotency_clash(error):
            raise
        # The original committed while we waited. Start a clean transaction,
        # read what it wrote, and hand it back to whoever owns it.
        await db.rollback()
        existing = await db.scalar(select(Order).where(Order.idempotency_key == idempotency_key))
        if existing is None:  # pragma: no cover - the violation proves it exists
            raise
        return _replay(existing, user=user, customer=customer)

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

        primary = next(
            (image.url for image in sorted(product.images, key=lambda i: i.position)), ""
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
    shipping = calc_shipping(subtotal)

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

    return order


async def list_for_user(db: AsyncSession, user_id: UUID) -> list[Order]:
    stmt = (
        select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(100)
    )
    return list((await db.scalars(stmt)).unique().all())


async def get_by_number(
    db: AsyncSession, order_number: str, *, user: User | None, contact: str | None = None
) -> Order:
    """შეკვეთის წაკითხვა ნომრით.

    შეკვეთის ნომერი თანმიმდევრობითია და გამოცნობადი, ამიტომ მარტო ნომრით
    წვდომა დაუშვებელია. ავტორიზებული თავისას ხედავს; სტუმარმა ელ. ფოსტა ან
    ტელეფონი უნდა დაამთხვიოს. ორივე შემთხვევაში უარი 404-ია და არა 403.

    `contact` is whichever of the two the guest gave at checkout; it is
    compared through services/contact.py, the same helper that decides whether
    a repeated Idempotency-Key belongs to the caller. The two answers have to
    agree - an order a guest can read is one they could have replayed.

    ⚠️ The value must never reach a URL. It used to arrive as `?email=` while
    actually carrying a phone number, which put a customer's phone in every
    access log, proxy log and browser history entry.
    """
    order = await db.scalar(select(Order).where(Order.order_number == order_number))
    if order is None:
        raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")

    if user is not None and order.user_id == user.id:
        return order

    if contact_matches(contact, email=order.guest_email, phone=order.guest_phone):
        return order

    # Deliberately the same answer as "no such order": a different one would
    # turn the sequential order numbers into a way to enumerate real orders.
    raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")


async def cancel(db: AsyncSession, order: Order, *, actor_id: UUID | None = None) -> Order:
    """გაუქმება მარაგს აბრუნებს — სხვაგვარად ჩამოწერილი ერთეულები დაიკარგება.

    The order row is locked here rather than by the caller. Relying on a
    docstring to say "lock this first" means the one caller that forgets
    restocks an order twice, and the second refund only shows up as inventory
    that never reconciles.

    Lock order is fixed: the order row first, then its products by ascending
    id - the same sequence checkout follows, so a cancellation racing an order
    for the same products cannot deadlock against it.
    """
    # populate_existing: the caller handed us an instance this session already
    # loaded. Without it the re-read returns that cached object with the status
    # it had before the lock, and two concurrent cancellations would both see
    # "pending" and both return the stock - which is the bug the lock is for.
    locked = await db.scalar(select(Order.id).where(Order.id == order.id).with_for_update())
    if locked is None:
        raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")
    fresh = await db.scalar(
        select(Order).where(Order.id == order.id).execution_options(populate_existing=True)
    )
    if fresh is None:  # pragma: no cover - the lock above already proved it exists
        raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")

    if fresh.status in {"shipped", "delivered", "cancelled"}:
        raise ConflictError("Order can no longer be cancelled", code="ORDER_NOT_CANCELLABLE")

    # id-ით დალაგებული — იგივე წესი, რაც შექმნისას.
    # `adjust_stock` locks each product row before reading it, so the read and
    # the write are one atomic step; it is also the only path that writes the
    # inventory_movements row, which a bare `stock = stock + n` would skip.
    for item in sorted(fresh.items, key=lambda i: i.product_id):
        await adjust_stock(
            db,
            item.product_id,
            item.quantity,
            REASON_ORDER_CANCELLED,
            actor_id=actor_id,
            order_id=fresh.id,
        )
    fresh.status = "cancelled"
    await db.flush()
    return fresh
