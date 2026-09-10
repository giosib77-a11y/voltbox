"""Admin brand endpoints.

What it does: the HTTP layer for managing brands.
Where it fits: thin routes over services/admin_catalog.py, mounted on
admin_router so require_admin has already run.
Notes: a brand cannot be deleted while products reference it - the response says
how many, so the admin knows what to fix rather than seeing a foreign-key error.
"""

from uuid import UUID

from fastapi import APIRouter, Request, status

from app.core.deps import AdminUser, Db
from app.schemas.admin_catalog import BrandAdminOut, BrandCreate, BrandUpdate
from app.services import admin_catalog, audit

router = APIRouter(prefix="/brands", tags=["admin"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", summary="List brands", response_model=list[BrandAdminOut])
async def list_brands(db: Db) -> list[BrandAdminOut]:
    return [BrandAdminOut.model_validate(row) for row in await admin_catalog.list_brands(db)]


@router.get("/{brand_id}", summary="Get a brand", response_model=BrandAdminOut)
async def get_brand(db: Db, brand_id: UUID) -> BrandAdminOut:
    return BrandAdminOut.model_validate(await admin_catalog.get_brand(db, brand_id))


@router.post(
    "", summary="Create a brand", status_code=status.HTTP_201_CREATED, response_model=BrandAdminOut
)
async def create_brand(
    request: Request, db: Db, admin: AdminUser, payload: BrandCreate
) -> BrandAdminOut:
    brand = await admin_catalog.create_brand(db, payload.model_dump(exclude_unset=True))
    await audit.record(
        db,
        actor_id=admin.id,
        action="brand.create",
        entity_type="brand",
        entity_id=str(brand.id),
        changes={"slug": brand.slug, "name": brand.name},
        ip=_client_ip(request),
    )
    await db.commit()
    return BrandAdminOut.model_validate(await admin_catalog.get_brand(db, brand.id))


@router.patch("/{brand_id}", summary="Update a brand", response_model=BrandAdminOut)
async def update_brand(
    request: Request, db: Db, admin: AdminUser, brand_id: UUID, payload: BrandUpdate
) -> BrandAdminOut:
    _, before, after = await admin_catalog.update_brand(
        db, brand_id, payload.model_dump(exclude_unset=True)
    )
    await audit.record(
        db,
        actor_id=admin.id,
        action="brand.update",
        entity_type="brand",
        entity_id=str(brand_id),
        changes=audit.diff(before, after),
        ip=_client_ip(request),
    )
    await db.commit()
    return BrandAdminOut.model_validate(await admin_catalog.get_brand(db, brand_id))


@router.delete("/{brand_id}", summary="Delete a brand", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(request: Request, db: Db, admin: AdminUser, brand_id: UUID) -> None:
    snapshot = await admin_catalog.get_brand(db, brand_id)
    await admin_catalog.delete_brand(db, brand_id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="brand.delete",
        entity_type="brand",
        entity_id=str(brand_id),
        changes={"slug": snapshot["slug"], "name": snapshot["name"]},
        ip=_client_ip(request),
    )
    await db.commit()
