"""Admin order endpoints.

What it does: the filtered order list (live or trash), the detail view, status
changes, and moving an order to the trash and back.
Where it fits: thin routes over services/admin_orders.py,
services/order_status.py and services/order_trash.py, mounted on admin_router.
Notes: a status change goes through the state machine and nowhere else, so the
side effects (restocking a cancellation, writing history) cannot be skipped by
adding another endpoint later. Trash and restore never touch stock, and write an
audit row only when they changed something - a repeated click is a no-op, not a
second log entry.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.core.config import settings
from app.core.deps import AdminUser, Db
from app.schemas.admin_orders import (
    OrderDetailOut,
    OrderPage,
    StatusChangeRequest,
    StatusHistoryOut,
)
from app.services import admin_orders, audit, order_status, order_trash

router = APIRouter(prefix="/orders", tags=["admin"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _detail(db: Db, order_id: UUID) -> OrderDetailOut:
    payload = await admin_orders.get_order(db, order_id)
    payload["history"] = [
        StatusHistoryOut.model_validate(entry) for entry in await order_status.history(db, order_id)
    ]
    return OrderDetailOut.model_validate(payload)


@router.get("", summary="List orders", response_model=OrderPage)
async def list_orders(
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.default_page_size,
    q: str | None = None,
    status: str | None = None,
    date_from: Annotated[str | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[str | None, Query(alias="dateTo")] = None,
    trash: bool = False,
) -> OrderPage:
    result = await admin_orders.list_orders(
        db,
        page=page,
        limit=limit,
        q=q,
        status=status,
        date_from=admin_orders.parse_date(date_from, "dateFrom"),
        date_to=admin_orders.parse_date(date_to, "dateTo"),
        trash=trash,
    )
    return OrderPage.model_validate(result)


@router.get("/{order_id}", summary="Get an order", response_model=OrderDetailOut)
async def get_order(db: Db, order_id: UUID) -> OrderDetailOut:
    return await _detail(db, order_id)


@router.post(
    "/{order_id}/status", summary="Change an order's status", response_model=OrderDetailOut
)
async def change_status(
    request: Request, db: Db, admin: AdminUser, order_id: UUID, payload: StatusChangeRequest
) -> OrderDetailOut:
    order = await order_status.transition(
        db, order_id, payload.to, actor_id=admin.id, note=payload.note
    )
    await audit.record(
        db,
        actor_id=admin.id,
        action="order.status",
        entity_type="order",
        entity_id=str(order_id),
        changes={"status": order.status, "note": payload.note},
        ip=_client_ip(request),
    )
    await db.commit()
    return await _detail(db, order_id)


@router.post(
    "/{order_id}/trash", summary="Move an order to the trash", response_model=OrderDetailOut
)
async def trash_order(request: Request, db: Db, admin: AdminUser, order_id: UUID) -> OrderDetailOut:
    order, changed = await order_trash.trash(db, order_id)
    if changed:
        await audit.record(
            db,
            actor_id=admin.id,
            action="order.trash",
            entity_type="order",
            entity_id=str(order_id),
            changes={"status": order.status, "deletedAt": order.deleted_at},
            ip=_client_ip(request),
        )
    await db.commit()
    return await _detail(db, order_id)


@router.post(
    "/{order_id}/restore", summary="Take an order out of the trash", response_model=OrderDetailOut
)
async def restore_order(
    request: Request, db: Db, admin: AdminUser, order_id: UUID
) -> OrderDetailOut:
    order, changed = await order_trash.restore(db, order_id)
    if changed:
        await audit.record(
            db,
            actor_id=admin.id,
            action="order.restore",
            entity_type="order",
            entity_id=str(order_id),
            changes={"status": order.status, "deletedAt": None},
            ip=_client_ip(request),
        )
    await db.commit()
    return await _detail(db, order_id)
