"""Admin category endpoints.

What it does: the HTTP layer for managing categories and their filter config.
Where it fits: thin routes over services/admin_catalog.py, mounted on
admin_router so require_admin has already run.
Notes: every mutation writes an admin_audit_log row in the same transaction as
the change, so a rolled-back request leaves no log entry claiming it happened.
"""

from uuid import UUID

from fastapi import APIRouter, Request, status

from app.core.deps import AdminUser, Db
from app.schemas.admin_catalog import CategoryAdminOut, CategoryCreate, CategoryUpdate
from app.services import admin_catalog, audit

router = APIRouter(prefix="/categories", tags=["admin"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", summary="List categories", response_model=list[CategoryAdminOut])
async def list_categories(db: Db) -> list[CategoryAdminOut]:
    rows = await admin_catalog.list_categories(db)
    return [CategoryAdminOut.model_validate(row) for row in rows]


@router.get("/{category_id}", summary="Get a category", response_model=CategoryAdminOut)
async def get_category(db: Db, category_id: UUID) -> CategoryAdminOut:
    return CategoryAdminOut.model_validate(await admin_catalog.get_category(db, category_id))


@router.post(
    "",
    summary="Create a category",
    status_code=status.HTTP_201_CREATED,
    response_model=CategoryAdminOut,
)
async def create_category(
    request: Request, db: Db, admin: AdminUser, payload: CategoryCreate
) -> CategoryAdminOut:
    data = payload.model_dump(exclude_unset=True)
    # Pydantic models are not JSONB-serialisable; the storefront reads plain dicts.
    if "filters" in data:
        data["filters"] = [f.model_dump(exclude_none=True) for f in payload.filters]

    category = await admin_catalog.create_category(db, data)
    await audit.record(
        db,
        actor_id=admin.id,
        action="category.create",
        entity_type="category",
        entity_id=str(category.id),
        changes={"slug": category.slug, "name": category.name},
        ip=_client_ip(request),
    )
    await db.commit()
    return CategoryAdminOut.model_validate(await admin_catalog.get_category(db, category.id))


@router.patch("/{category_id}", summary="Update a category", response_model=CategoryAdminOut)
async def update_category(
    request: Request, db: Db, admin: AdminUser, category_id: UUID, payload: CategoryUpdate
) -> CategoryAdminOut:
    patch = payload.model_dump(exclude_unset=True)
    if "filters" in patch and payload.filters is not None:
        patch["filters"] = [f.model_dump(exclude_none=True) for f in payload.filters]

    _, before, after = await admin_catalog.update_category(db, category_id, patch)
    await audit.record(
        db,
        actor_id=admin.id,
        action="category.update",
        entity_type="category",
        entity_id=str(category_id),
        changes=audit.diff(before, after),
        ip=_client_ip(request),
    )
    await db.commit()
    return CategoryAdminOut.model_validate(await admin_catalog.get_category(db, category_id))


@router.delete(
    "/{category_id}", summary="Delete a category", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_category(request: Request, db: Db, admin: AdminUser, category_id: UUID) -> None:
    snapshot = await admin_catalog.get_category(db, category_id)
    await admin_catalog.delete_category(db, category_id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="category.delete",
        entity_type="category",
        entity_id=str(category_id),
        changes={"slug": snapshot["slug"], "name": snapshot["name"]},
        ip=_client_ip(request),
    )
    await db.commit()
