"""შეკვეთები და მათი პოზიციები.

ორივე ცხრილში snapshot-სვეტებია: პროდუქტის ფასის ან სახელის მოგვიანებითი
ცვლილება შეკვეთის ისტორიას არ უნდა გადაწეროს. იმავე მიზეზით მისამართიც და
მყიდველის მონაცემებიც jsonb-ად ინახება და არა FK-ით — შეკვეთა უნდა გადარჩეს
მისამართის ან ანგარიშის წაშლას.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey

ORDER_STATUSES = ("pending", "confirmed", "processing", "shipped", "delivered", "cancelled")


class Order(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "orders"

    order_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    guest_email: Mapped[str | None] = mapped_column(String(255))
    guest_phone: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")

    # frontend-ის `customer` ობიექტი უცვლელად: firstName, lastName, phone, city,
    # address, comment — ესეც snapshot-ია და მისამართის ცხრილს არ უკავშირდება
    customer: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    shipping_address: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    shipping: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="GEL")

    payment_method: Mapped[str] = mapped_column(String(32), nullable=False, server_default="cash")
    notes: Mapped[str | None] = mapped_column(Text)

    # ორმაგი გაგზავნისგან დაცვა: იგივე გასაღები → იგივე შეკვეთა და არა მეორე
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','confirmed','processing','shipped','delivered','cancelled')",
            name="status_allowed",
        ),
        # სტუმრის შეკვეთას მაინც უნდა ჰქონდეს საკონტაქტო არხი
        CheckConstraint(
            "user_id IS NOT NULL OR guest_email IS NOT NULL OR guest_phone IS NOT NULL",
            name="owner_or_guest_contact",
        ),
        CheckConstraint(
            "subtotal >= 0 AND shipping >= 0 AND total >= 0", name="totals_non_negative"
        ),
        Index("ix_orders_user_id_created_at", "user_id", text("created_at DESC")),
    )


class OrderStatusHistory(UUIDPrimaryKey, Base):
    """One row per status change - who moved the order, when, and why.

    Separate from admin_audit_log on purpose: an order's timeline is something
    the admin UI renders, and two records of one event drift apart eventually.
    """

    __tablename__ = "order_status_history"

    order_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    # SET NULL, not CASCADE: deleting the account must not erase what it did.
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)
    # clock_timestamp(), not now(): several transitions can land in one
    # transaction and must stay orderable.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("clock_timestamp()"), nullable=False
    )

    __table_args__ = (Index("ix_order_status_history_order", "order_id", text("created_at")),)


class OrderItem(UUIDPrimaryKey, Base):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    # RESTRICT — პროდუქტის წაშლა არ უნდა ანგრევდეს ისტორიას
    product_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )

    product_name: Mapped[str] = mapped_column(String(300), nullable=False)
    product_slug: Mapped[str] = mapped_column(String(200), nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0 AND line_total >= 0", name="amounts_non_negative"),
        Index("ix_order_items_order_id", "order_id"),
    )
