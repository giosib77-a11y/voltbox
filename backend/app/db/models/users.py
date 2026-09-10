"""მომხმარებლები, მისამართები და refresh-ტოკენები.

frontend-ის `User` ტიპს `firstName` + `lastName` აქვს (და არა ერთიანი `full_name`),
ამიტომ სქემაც ასეა — იხ. `../frontend/src/types.js`.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class User(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "users"

    # CITEXT — ელ. ფოსტის უნიკალურობა რეგისტრისადმი გულგრილი უნდა იყოს,
    # თორემ Giorgi@x.ge და giorgi@x.ge ორ სხვადასხვა ანგარიშად დარეგისტრირდება
    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    phone: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="customer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    addresses: Mapped[list["Address"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class Address(UUIDPrimaryKey, Timestamps, Base):
    """მისამართი.

    სავალდებულო ველები frontend-ის ფორმას მისდევს (`label`, `city`, `address`),
    დანარჩენი (`full_name`, `phone`, `apartment`, `postal_code`) nullable-ია —
    ისინი მომავალი გაფართოებისთვისაა და ახლა frontend მათ არ აგზავნის.
    """

    __tablename__ = "addresses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    address_line: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(32))
    apartment: Mapped[str | None] = mapped_column(String(50))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    user: Mapped[User] = relationship(back_populates="addresses")

    __table_args__ = (
        # ერთ მომხმარებელს მხოლოდ ერთი ძირითადი მისამართი — ბაზის დონეზე,
        # რომ პარალელურმა მოთხოვნებმა ორი default ვერ შექმნას
        Index(
            "uq_addresses_one_default_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
        Index("ix_addresses_user_id", "user_id"),
    )


class RefreshToken(UUIDPrimaryKey, Base):
    """refresh-ტოკენი მხოლოდ hash-ის სახით ინახება.

    ბაზის გაჟონვისას ნედლი ტოკენები ვერ გამოიყენება. rotation-on-use:
    გამოყენებულ ტოკენს `revoked_at` ეწერება და ახალი გაიცემა.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    __table_args__ = (Index("ix_refresh_tokens_user_id", "user_id"),)
