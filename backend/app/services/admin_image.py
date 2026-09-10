"""Product image management.

What it does: upload, reorder, choose the primary image and delete.
Where it fits: called by app/api/v1/routes/admin/images.py; storage itself is
behind services/storage.py so tests run against an in-memory backend.

Notes: `product_images` has a partial unique index allowing one primary row per
product, which is checked immediately. That makes the order of writes matter -
see set_primary.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import OrderItem, Product, ProductImage
from app.services.storage import StorageBackend, object_key, validate_image

MAX_IMAGES_PER_PRODUCT = 12

CONTENT_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


async def _load_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found", code="PRODUCT_NOT_FOUND")
    return product


async def _images(db: AsyncSession, product_id: uuid.UUID) -> list[ProductImage]:
    stmt = (
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(ProductImage.position, ProductImage.id)
    )
    return list((await db.scalars(stmt)).all())


async def add_image(
    db: AsyncSession,
    storage: StorageBackend,
    product_id: uuid.UUID,
    *,
    data: bytes,
    declared_type: str | None,
) -> ProductImage:
    """Validate, store, then record. Returns the new row."""
    await _load_product(db, product_id)

    existing = await _images(db, product_id)
    if len(existing) >= MAX_IMAGES_PER_PRODUCT:
        raise ConflictError(
            f"A product may have at most {MAX_IMAGES_PER_PRODUCT} images",
            code="TOO_MANY_IMAGES",
        )

    _, extension = validate_image(data, declared_type)
    key = object_key(product_id, extension)
    url = await storage.upload(key, data, CONTENT_TYPES[extension])

    image = ProductImage(
        product_id=product_id,
        url=url,
        alt="",
        position=len(existing),
        # The first image becomes primary so a product is never left without one.
        is_primary=not existing,
    )
    db.add(image)
    await db.flush()
    return image


async def reorder(
    db: AsyncSession, product_id: uuid.UUID, ordered_ids: list[uuid.UUID]
) -> list[ProductImage]:
    """Apply a full ordering. The list must match the product's images exactly.

    Accepting a partial list would leave the rest at stale positions, and the
    resulting order would depend on the id tiebreaker rather than on intent.
    """
    images = await _images(db, product_id)
    if not images:
        raise NotFoundError("This product has no images", code="NO_IMAGES")

    current = {image.id for image in images}
    if set(ordered_ids) != current or len(ordered_ids) != len(images):
        raise ValidationError(
            "The list must contain every image of this product exactly once",
            code="INCOMPLETE_IMAGE_ORDER",
            details={"expected": [str(i) for i in current]},
        )

    by_id = {image.id: image for image in images}
    for position, image_id in enumerate(ordered_ids):
        by_id[image_id].position = position
    await db.flush()
    return await _images(db, product_id)


async def set_primary(
    db: AsyncSession, product_id: uuid.UUID, image_id: uuid.UUID
) -> list[ProductImage]:
    """Make one image primary.

    The unset must be flushed before the set. `uq_product_images_one_primary` is
    a partial unique index, checked per statement, and SQLAlchemy is free to
    order the UPDATEs within a single flush however it likes - so doing both in
    one flush can transiently produce two primary rows and fail.
    """
    images = await _images(db, product_id)
    target = next((image for image in images if image.id == image_id), None)
    if target is None:
        raise NotFoundError("Image not found", code="IMAGE_NOT_FOUND")

    for image in images:
        if image.is_primary and image.id != image_id:
            image.is_primary = False
    await db.flush()

    target.is_primary = True
    await db.flush()
    return await _images(db, product_id)


async def delete_image(
    db: AsyncSession, storage: StorageBackend, product_id: uuid.UUID, image_id: uuid.UUID
) -> None:
    """Remove the row, and the stored object only when nothing else needs it."""
    images = await _images(db, product_id)
    target = next((image for image in images if image.id == image_id), None)
    if target is None:
        raise NotFoundError("Image not found", code="IMAGE_NOT_FOUND")

    url = target.url
    was_primary = target.is_primary

    await db.delete(target)
    await db.flush()

    remaining = await _images(db, product_id)
    # Repack positions so they stay 0..n-1 instead of developing gaps.
    for position, image in enumerate(remaining):
        image.position = position
    if was_primary and remaining:
        await db.flush()
        remaining[0].is_primary = True
    await db.flush()

    # Order items snapshot the image URL. Deleting the object would turn a past
    # order's thumbnail into a broken link, so the row goes and the file stays.
    referenced = await db.scalar(
        select(func.count()).select_from(OrderItem).where(OrderItem.image_url == url)
    )
    if not referenced:
        key = _key_from_url(url)
        if key:
            await storage.delete(key)


def _key_from_url(url: str) -> str | None:
    """Recover the object key from a stored URL.

    Returns None for anything that does not look like one of our keys, so a URL
    that was set by an import script or typed by hand is never used to delete
    something in the bucket.
    """
    marker = "products/"
    index = url.find(marker)
    if index == -1:
        return None
    return url[index:]
