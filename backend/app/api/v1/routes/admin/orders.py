"""Admin order endpoints.

What it does: the filtered order list (live or trash), the detail view, status
changes, moving an order to the trash and back, and deleting a trashed order
for good.
Where it fits: thin routes over services/admin_orders.py,
services/order_status.py and services/order_trash.py, mounted on admin_router.
Notes: a status change goes through the state machine and nowhere else, so the
side effects (restocking a cancellation, writing history) cannot be skipped by
adding another endpoint later. Trash, restore and delete never touch stock.
Trash and restore write an audit row only when they changed something - a
repeated click is a no-op, not a second log entry; the delete writes its
`order.purge` row inside the service. Opening the list first sweeps the
orders whose 30 days in the trash are up, in a transaction of its own.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

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
    # Lazy retention sweep (Decision Log 2026-10-18): committed on its own before
    # the list query, so a failing list cannot roll the deletions back, and a
    # sweep that finds nothing writes nothing.
    if await order_trash.purge_expired(db):
        await db.commit()
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


@router.delete(
    "/{order_id}",
    summary="Delete a trashed order for good",
    status_code=204,
    response_class=Response,
)
async def delete_order(request: Request, db: Db, admin: AdminUser, order_id: UUID) -> Response:
    await order_trash.delete_forever(db, order_id, actor_id=admin.id, ip=_client_ip(request))
    await db.commit()
    return Response(status_code=204)
