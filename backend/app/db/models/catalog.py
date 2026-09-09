"""კატალოგი — კატეგორიები, ბრენდები, პროდუქტები, სურათები.

⚠️ სქემა frontend-ის კონტრაქტს მისდევს (`src/types.js`), რაც ნიშნავს რამდენიმე
სვეტს, რომელიც საწყის ტექნიკურ დავალებაში არ იყო:
  · categories.icon, categories.filters — FilterSidebar სრულად ამ კონფიგზეა აგებული
  · products.short_description, is_new, reviews_count — ბარათებზე ჩანს
  · brands.country — პროდუქტის „მახასიათებლების“ ცხრილში brandCountry-დ ჩანს
ამ სვეტების გარეშე frontend-ის ნაწილები უბრალოდ არ დაიხატება.
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class Category(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    short_name: Mapped[str] = mapped_column(String(150), nullable=False, server_default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    icon: Mapped[str] = mapped_column(String(50), nullable=False, server_default="Package")
    # ფილტრების კონფიგი data-driven-ია: [{key,label,type,match?}]
    # ახალი კატეგორიის დამატება არც backend-ის და არც frontend-ის კოდს არ ცვლის
    filters: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    image_url: Mapped[str | None] = mapped_column(Text)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Brand(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "brands"

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    country: Mapped[str | None] = mapped_column(String(100))
    logo_url: Mapped[str | None] = mapped_column(Text)

    products: Mapped[list["Product"]] = relationship(back_populates="brand")


class Product(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "products"

    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    sku: Mapped[str | None] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    short_description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="RESTRICT"), nullable=False
    )

    # ფული ყოველთვის numeric — float-ს დამრგვალების შეცდომები შემოაქვს
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    stock: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # frontend-ის LOW_STOCK_THRESHOLD = 3 (და არა 5, როგორც დავალებაში ეწერა)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")

    specs: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )

    rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False, server_default="0")
    reviews_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_new: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    category: Mapped[Category] = relationship(back_populates="products", lazy="joined")
    brand: Mapped[Brand] = relationship(back_populates="products", lazy="joined")
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.position",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("old_price IS NULL OR old_price > price", name="old_price_above_price"),
        CheckConstraint("stock >= 0", name="stock_non_negative"),
        CheckConstraint("rating >= 0 AND rating <= 5", name="rating_within_range"),
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_brand_id", "brand_id"),
        Index("ix_products_price", "price"),
        Index("ix_products_created_at", text("created_at DESC")),
        Index("ix_products_specs", "specs", postgresql_using="gin"),
        Index("ix_products_tags", "tags", postgresql_using="gin"),
        # ქართულ ტექსტს Postgres-ის FTS ლექსიკონი არ აქვს, ამიტომ ძებნა
        # trigram-მსგავსებაზე დგას — ინდექსი აქვე ცხადდება, რომ მოდელი და
        # მიგრაცია ერთმანეთს არ დაშორდნენ (autogenerate drift)
        Index(
            "ix_products_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class ProductImage(UUIDPrimaryKey, Base):
    __tablename__ = "product_images"

    product_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    alt: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    product: Mapped[Product] = relationship(back_populates="images")

    __table_args__ = (
        # ერთი მთავარი სურათი პროდუქტზე — ბაზის დონეზე გარანტირებული
        Index(
            "uq_product_images_one_primary",
            "product_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
        Index("ix_product_images_product_id", "product_id"),
    )
