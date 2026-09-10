"""Admin customer endpoints.

What it does: the customer list, one customer's detail, and blocking or
unblocking an account.
Where it fits: thin routes over services/admin_customers.py.
Notes: responses go through explicit models, never an ORM object - that is what
keeps password_hash and token hashes out of the payload.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.core.config import settings
from app.core.deps import AdminUser, Db
from app.schemas.admin_customers import BlockRequest, CustomerDetailOut, CustomerPage
from app.services import admin_customers, audit

router = APIRouter(prefix="/customers", tags=["admin"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", summary="List customers", response_model=CustomerPage)
async def list_customers(
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.default_page_size,
    q: str | None = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
) -> CustomerPage:
    result = await admin_customers.list_customers(
        db, page=page, limit=limit, q=q, is_active=is_active
    )
    return CustomerPage.model_validate(result)


@router.get("/{user_id}", summary="Get a customer", response_model=CustomerDetailOut)
async def get_customer(db: Db, user_id: UUID) -> CustomerDetailOut:
    return CustomerDetailOut.model_validate(await admin_customers.get_customer(db, user_id))


@router.post("/{user_id}/active", summary="Block or unblock", response_model=CustomerDetailOut)
async def set_active(
    request: Request, db: Db, admin: AdminUser, user_id: UUID, payload: BlockRequest
) -> CustomerDetailOut:
    await admin_customers.set_active(db, user_id, payload.is_active, actor=admin)
    await audit.record(
        db,
        actor_id=admin.id,
        action="customer.block" if not payload.is_active else "customer.unblock",
        entity_type="user",
        entity_id=str(user_id),
        changes={"isActive": payload.is_active},
        ip=_client_ip(request),
    )
    await db.commit()
    return CustomerDetailOut.model_validate(await admin_customers.get_customer(db, user_id))
