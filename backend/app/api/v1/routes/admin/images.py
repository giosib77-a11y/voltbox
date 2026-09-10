"""Product image endpoints.

What it does: upload, reorder, set primary and delete product images.
Where it fits: thin routes over services/admin_image.py, mounted on
admin_router so require_admin has already run.
Notes: the storage backend is resolved per request through a dependency, so
tests can swap in the in-memory one without touching the routes.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from app.core.deps import AdminUser, Db
from app.schemas.admin_product import ImageOrderRequest, ProductImageOut
from app.services import admin_image, audit
from app.services.storage import StorageBackend, get_storage

router = APIRouter(prefix="/products/{product_id}/images", tags=["admin"])

Storage = Annotated[StorageBackend, Depends(get_storage)]


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post(
    "",
    summary="Upload a product image",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductImageOut,
)
async def upload_image(
    request: Request,
    db: Db,
    admin: AdminUser,
    storage: Storage,
    product_id: UUID,
    file: Annotated[UploadFile, File()],
) -> ProductImageOut:
    data = await file.read()
    image = await admin_image.add_image(
        db, storage, product_id, data=data, declared_type=file.content_type
    )
    await audit.record(
        db,
        actor_id=admin.id,
        action="product.image.add",
        entity_type="product",
        entity_id=str(product_id),
        changes={"imageId": str(image.id), "url": image.url},
        ip=_client_ip(request),
    )
    await db.commit()
    return ProductImageOut.model_validate(image)


@router.put("/order", summary="Reorder product images", response_model=list[ProductImageOut])
async def reorder_images(
    request: Request,
    db: Db,
    admin: AdminUser,
    product_id: UUID,
    payload: ImageOrderRequest,
) -> list[ProductImageOut]:
    images = await admin_image.reorder(db, product_id, payload.image_ids)
    await audit.record(
        db,
        actor_id=admin.id,
        action="product.image.reorder",
        entity_type="product",
        entity_id=str(product_id),
        changes={"order": [str(image.id) for image in images]},
        ip=_client_ip(request),
    )
    await db.commit()
    return [ProductImageOut.model_validate(image) for image in images]


@router.post(
    "/{image_id}/primary", summary="Set the primary image", response_model=list[ProductImageOut]
)
async def set_primary(
    request: Request, db: Db, admin: AdminUser, product_id: UUID, image_id: UUID
) -> list[ProductImageOut]:
    images = await admin_image.set_primary(db, product_id, image_id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="product.image.primary",
        entity_type="product",
        entity_id=str(product_id),
        changes={"primaryId": str(image_id)},
        ip=_client_ip(request),
    )
    await db.commit()
    return [ProductImageOut.model_validate(image) for image in images]


@router.delete(
    "/{image_id}", summary="Delete a product image", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_image(
    request: Request,
    db: Db,
    admin: AdminUser,
    storage: Storage,
    product_id: UUID,
    image_id: UUID,
) -> None:
    await admin_image.delete_image(db, storage, product_id, image_id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="product.image.delete",
        entity_type="product",
        entity_id=str(product_id),
        changes={"imageId": str(image_id)},
        ip=_client_ip(request),
    )
    await db.commit()
