"""შეკვეთების ბიზნეს-ლოგიკა — პროექტის ყველაზე მაღალი რისკის ზონა.

მთელი შექმნა ერთ ტრანზაქციაშია. თანმიმდევრობა და მიზეზები:

  1. პროდუქტების row-ები იბლოკება `FOR UPDATE`-ით, **id-ით დალაგებულად**.
     დალაგება აუცილებელია: ორი პარალელური შეკვეთა, რომლებიც ერთსა და იმავე ორ
     პროდუქტს სხვადასხვა რიგით ბლოკავს, ურთიერთბლოკირებას (deadlock) გამოიწვევს.
  2. ფასი *ყოველთვის* ბაზიდან მოდის. კლიენტის გამოგზავნილი ფასი არსად არ
     გამოიყენება — ეს ფასის გაყალბების ვექტორია.
  3. მარაგი ატომურად ჩამოიწერება პირობით `WHERE stock >= :qty`. `rowcount != 1`
     ნიშნავს, რომ ვიღაცამ დაგვასწრო — ტრანზაქცია ჩავარდება.
  4. სახელი, slug, სურათი და ფასი შეკვეთაში snapshot-ად ინახება: მოგვიანებით
     ფასის ცვლილება ისტორიას არ უნდა გადაწეროს.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import CursorResult, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import Order, OrderItem, Product, User

MAX_QUANTITY = 99


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
            # ორმაგად გაგზავნილი checkout — იმავე შეკვეთას ვაბრუნებთ და მეორეს არ ვქმნით
            return existing

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

    products = await _lock_products(db, sorted(quantities))

    order_items: list[OrderItem] = []
    subtotal = Decimal("0")

    for product_id in sorted(quantities):
        qty = quantities[product_id]
        product = products.get(product_id)
        if product is None or not product.is_active:
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

    # მარაგის ატომური ჩამოწერა. row უკვე დაბლოკილია, მაგრამ პირობა მაინც რჩება —
    # ის ბაზის დონეზე იცავს იმ შემთხვევასაც, თუ ბლოკირება ოდესმე მოიხსნება
    for product_id in sorted(quantities):
        result: CursorResult[Any] = await db.execute(  # type: ignore[assignment]
            update(Product)
            .where(Product.id == product_id, Product.stock >= quantities[product_id])
            .values(stock=Product.stock - quantities[product_id])
        )
        # rowcount != 1 ნიშნავს, რომ ვიღაცამ დაგვასწრო და მარაგი აღარ ჰყოფნის
        if result.rowcount != 1:
            raise ConflictError(
                "Not enough stock",
                code="INSUFFICIENT_STOCK",
                details={"productId": str(product_id)},
            )

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
        subtotal=subtotal,
        shipping=shipping,
        total=money(subtotal + shipping),
        currency=settings.currency,
        payment_method=payment_method,
        notes=customer.get("comment") or None,
        idempotency_key=idempotency_key,
        items=order_items,
    )
    db.add(order)
    await db.flush()
    return order


async def list_for_user(db: AsyncSession, user_id: UUID) -> list[Order]:
    stmt = (
        select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(100)
    )
    return list((await db.scalars(stmt)).unique().all())


async def get_by_number(
    db: AsyncSession, order_number: str, *, user: User | None, email: str | None = None
) -> Order:
    """შეკვეთის წაკითხვა ნომრით.

    შეკვეთის ნომერი თანმიმდევრობითია და გამოცნობადი, ამიტომ მარტო ნომრით
    წვდომა დაუშვებელია. ავტორიზებული თავისას ხედავს; სტუმარმა ელ. ფოსტა ან
    ტელეფონი უნდა დაამთხვიოს. ორივე შემთხვევაში უარი 404-ია და არა 403.
    """
    order = await db.scalar(select(Order).where(Order.order_number == order_number))
    if order is None:
        raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")

    if user is not None and order.user_id == user.id:
        return order

    contact = (email or "").strip().lower()
    if contact and contact in {
        (order.guest_email or "").lower(),
        (order.guest_phone or "").lower(),
    }:
        return order

    raise NotFoundError("Order not found", code="ORDER_NOT_FOUND")


async def cancel(db: AsyncSession, order: Order) -> Order:
    """გაუქმება მარაგს აბრუნებს — სხვაგვარად ჩამოწერილი ერთეულები დაიკარგება."""
    if order.status in {"shipped", "delivered", "cancelled"}:
        raise ConflictError("Order can no longer be cancelled", code="ORDER_NOT_CANCELLABLE")

    for item in order.items:
        await db.execute(
            update(Product)
            .where(Product.id == item.product_id)
            .values(stock=Product.stock + item.quantity)
        )
    order.status = "cancelled"
    await db.flush()
    return order
