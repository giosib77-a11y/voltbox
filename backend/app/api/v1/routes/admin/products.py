"""Admin product endpoints: list, get, create, update, archive, duplicate, delete.

What it does: the HTTP layer for managing products from the admin panel.
Where it fits: thin routes over services/admin_product.py and
services/inventory.py, mounted on admin_router so require_admin has already run.
Notes: stock is never written here after creation - use the inventory endpoints,
so every change lands in inventory_movements.
"""

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.config import settings
from app.core.deps import AdminUser, Db
from app.schemas.admin_product import (
    ProductAdminOut,
    ProductCreate,
    ProductPage,
    ProductUpdate,
)
from app.services import admin_product, audit
from app.services.storage import StorageBackend, get_storage

router = APIRouter(prefix="/products", tags=["admin"])

Storage = Annotated[StorageBackend, Depends(get_storage)]


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", summary="List products", response_model=ProductPage)
async def list_products(
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_size)] = settings.default_page_size,
    sort: str = admin_product.DEFAULT_SORT,
    q: str | None = None,
    category_id: Annotated[UUID | None, Query(alias="categoryId")] = None,
    brand_id: Annotated[UUID | None, Query(alias="brandId")] = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
    include_archived: Annotated[bool, Query(alias="includeArchived")] = False,
    is_featured: Annotated[bool | None, Query(alias="isFeatured")] = None,
    is_new: Annotated[bool | None, Query(alias="isNew")] = None,
    low_stock: Annotated[bool | None, Query(alias="lowStock")] = None,
    price_min: Annotated[Decimal | None, Query(alias="priceMin", ge=0)] = None,
    price_max: Annotated[Decimal | None, Query(alias="priceMax", ge=0)] = None,
) -> ProductPage:
    result = await admin_product.list_products(
        db,
        page=page,
        limit=limit,
        sort=sort,
        q=q,
        category_id=category_id,
        brand_id=brand_id,
        is_active=is_active,
        include_archived=include_archived,
        is_featured=is_featured,
        is_new=is_new,
        low_stock=low_stock,
        price_min=price_min,
        price_max=price_max,
    )
    return ProductPage.model_validate(result)


@router.get("/{product_id}", summary="Get a product", response_model=ProductAdminOut)
async def get_product(db: Db, product_id: UUID) -> ProductAdminOut:
    return ProductAdminOut.model_validate(await admin_product.get_product(db, product_id))


@router.post(
    "",
    summary="Create a product",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductAdminOut,
)
async def create_product(
    request: Request, db: Db, admin: AdminUser, payload: ProductCreate
) -> ProductAdminOut:
    product = await admin_product.create_product(
        db, payload.model_dump(exclude_unset=True), actor_id=admin.id
    )
    await audit.record(
        db,
        actor_id=admin.id,
        action="product.create",
        entity_type="product",
        entity_id=str(product.id),
        changes={"slug": product.slug, "name": product.name, "sku": product.sku},
        ip=_client_ip(request),
    )
    await db.commit()
    return ProductAdminOut.model_validate(await admin_product.get_product(db, product.id))


@router.patch("/{product_id}", summary="Update a product", response_model=ProductAdminOut)
async def update_product(
    request: Request, db: Db, admin: AdminUser, product_id: UUID, payload: ProductUpdate
) -> ProductAdminOut:
    _, before, after = await admin_product.update_product(
        db, product_id, payload.model_dump(exclude_unset=True)
    )
    await audit.record(
        db,
        actor_id=admin.id,
        action="product.update",
        entity_type="product",
        entity_id=str(product_id),
        changes=audit.diff(before, after),
        ip=_client_ip(request),
    )
    await db.commit()
    return ProductAdminOut.model_validate(await admin_product.get_product(db, product_id))


@router.post("/{product_id}/archive", summary="Archive a product", response_model=ProductAdminOut)
async def archive_product(
    request: Request, db: Db, admin: AdminUser, product_id: UUID
) -> ProductAdminOut:
    product = await admin_product.archive_product(db, product_id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="product.archive",
        entity_type="product",
        entity_id=str(product_id),
        changes={"archivedAt": product.archived_at.isoformat() if product.archived_at else None},
        ip=_client_ip(request),
    )
    await db.commit()
    return ProductAdminOut.model_validate(await admin_product.get_product(db, product_id))


@router.post(
    "/{product_id}/unarchive", summary="Unarchive a product", response_model=ProductAdminOut
)
async def unarchive_product(
    request: Request, db: Db, admin: AdminUser, product_id: UUID
) -> ProductAdminOut:
    await admin_product.unarchive_product(db, product_id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="product.unarchive",
        entity_type="product",
        entity_id=str(product_id),
        changes={"archivedAt": None},
        ip=_client_ip(request),
    )
    await db.commit()
    return ProductAdminOut.model_validate(await admin_product.get_product(db, product_id))


@router.post(
    "/{product_id}/duplicate",
    summary="Duplicate a product",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductAdminOut,
)
async def duplicate_product(
    request: Request, db: Db, admin: AdminUser, product_id: UUID
) -> ProductAdminOut:
    copy = await admin_product.duplicate_product(db, product_id, actor_id=admin.id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="product.duplicate",
        entity_type="product",
        entity_id=str(copy.id),
        changes={"sourceId": str(product_id), "slug": copy.slug},
        ip=_client_ip(request),
    )
    await db.commit()
    return ProductAdminOut.model_validate(await admin_product.get_product(db, copy.id))


@router.delete("/{product_id}", summary="Delete a product", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    request: Request, db: Db, admin: AdminUser, storage: Storage, product_id: UUID
) -> None:
    """Permanent. Answers 409 PRODUCT_IN_USE for a product that has been ordered."""
    removed = await admin_product.delete_product(db, storage, product_id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="product.delete",
        entity_type="product",
        entity_id=str(product_id),
        changes=removed,
        ip=_client_ip(request),
    )
    await db.commit()
