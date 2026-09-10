"""Customer management for the admin panel.

What it does: the customer list with order aggregates, one customer's detail,
and blocking or unblocking an account.
Where it fits: called by app/api/v1/routes/admin/customers.py.

Notes: totals are computed with correlated subqueries rather than by loading a
customer's orders. On a shop with history that is the difference between a page
and a timeout, and the figures then match the dashboard by construction.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError
from app.db.models import ROLE_ADMIN, Order, User
from app.services import auth as auth_service
from app.services.admin_orders import normalize_phone

#: Cancelled orders do not count towards what a customer has spent - the goods
#: went back on the shelf. Same rule as the dashboard, deliberately.
EXCLUDED_FROM_SPEND = ("cancelled",)


def _orders_count_subquery() -> ColumnElement[int]:
    return (
        select(func.count())
        .select_from(Order)
        .where(Order.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )


def _total_spent_subquery() -> ColumnElement[Decimal]:
    return (
        select(func.coalesce(func.sum(Order.total), 0))
        .select_from(Order)
        .where(Order.user_id == User.id, Order.status.notin_(EXCLUDED_FROM_SPEND))
        .correlate(User)
        .scalar_subquery()
    )


async def list_customers(
    db: AsyncSession,
    *,
    page: int,
    limit: int,
    q: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    conditions: list[ColumnElement[bool]] = []
    if is_active is not None:
        conditions.append(User.is_active.is_(is_active))

    if q and q.strip():
        needle = q.strip()
        digits = normalize_phone(needle)
        clauses = [
            func.cast(User.email, String).ilike(f"%{needle}%"),
            User.first_name.ilike(f"%{needle}%"),
            User.last_name.ilike(f"%{needle}%"),
        ]
        if digits:
            stored = func.regexp_replace(func.coalesce(User.phone, ""), r"\D", "", "g")
            clauses.append(stored.ilike(f"%{digits}%"))
        conditions.append(or_(*clauses))

    total = await db.scalar(select(func.count()).select_from(User).where(*conditions))

    rows = await db.execute(
        select(User, _orders_count_subquery(), _total_spent_subquery())
        .where(*conditions)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset((page - 1) * limit)
    )

    total_count = int(total or 0)
    return {
        "items": [
            {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "role": user.role,
                "is_active": user.is_active,
                "orders_count": int(orders_count),
                "total_spent": Decimal(total_spent),
                "created_at": user.created_at,
            }
            for user, orders_count, total_spent in rows
        ],
        "total": total_count,
        "page": page,
        "total_pages": (total_count + limit - 1) // limit if limit else 0,
        "limit": limit,
    }


async def get_customer(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """One customer with their addresses and order history."""
    stmt = select(User).options(selectinload(User.addresses)).where(User.id == user_id)
    user = (await db.scalars(stmt)).unique().one_or_none()
    if user is None:
        raise NotFoundError("Customer not found", code="CUSTOMER_NOT_FOUND")

    orders = list(
        (
            await db.scalars(
                select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
            )
        )
        .unique()
        .all()
    )
    spent = sum(
        (order.total for order in orders if order.status not in EXCLUDED_FROM_SPEND),
        Decimal("0"),
    )

    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "role": user.role,
        "is_active": user.is_active,
        "orders_count": len(orders),
        "total_spent": spent,
        "created_at": user.created_at,
        "addresses": [
            {
                "id": address.id,
                "label": address.label,
                "city": address.city,
                "address_line": address.address_line,
                "phone": address.phone,
                "is_default": address.is_default,
            }
            for address in sorted(user.addresses, key=lambda a: (not a.is_default, a.label))
        ],
        "orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "total": order.total,
                "created_at": order.created_at,
            }
            for order in orders
        ],
    }


async def set_active(db: AsyncSession, user_id: uuid.UUID, active: bool, *, actor: User) -> User:
    """Block or unblock an account.

    Blocking revokes every refresh token: `require_admin` and `get_current_user`
    re-read the row, so the access token dies at once, but a live refresh token
    would keep minting new ones for up to 30 days.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("Customer not found", code="CUSTOMER_NOT_FOUND")

    if user.id == actor.id:
        # Locking yourself out of the panel is never the intent, and recovering
        # needs the CLI on the server.
        raise ConflictError("You cannot block your own account", code="CANNOT_BLOCK_SELF")
    if user.role == ROLE_ADMIN and not active:
        # Administrators are managed with the CLI, where demotion and blocking
        # are deliberate acts rather than a button next to a customer row.
        raise ConflictError(
            "Administrators cannot be blocked from the panel", code="CANNOT_BLOCK_ADMIN"
        )

    user.is_active = active
    if not active:
        await auth_service.revoke_all(db, user.id)
    await db.flush()
    return user
