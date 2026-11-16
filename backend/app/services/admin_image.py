"""Product image management.

What it does: upload, reorder, choose the primary image and delete.
Where it fits: called by app/api/v1/routes/admin/images.py; storage itself is
behind services/storage.py so tests run against an in-memory backend.

Notes: `product_images` has a partial unique index allowing one primary row per
product, which is checked immediately. That makes the order of writes matter -
see set_primary.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import OrderItem, Product, ProductImage
from app.services.storage import StorageBackend, object_key, shrink_to_fit, validate_image

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


#: One image is decoded at a time per worker process.
#:
#: Decoding and re-encoding is CPU work of seconds (a PNG used to take 6-8 s), so
#: it runs in a thread and the event loop keeps serving other requests. What
#: bounds the memory is this semaphore: the process never holds more than
#: MAX_IMAGE_DECODE_BYTES for an upload, and the deployment never more than
#: WEB_CONCURRENCY times that. A bare `to_thread` would let uploads decode in
#: parallel, up to the size of the loop's default executor - min(32, CPUs + 4),
#: not anyio's 40, since `asyncio.to_thread` does not use that pool - which is
#: gigabytes the free plan does not have. A second decode would not finish sooner
#: anyway on the fraction of a CPU Render gives.
#:
#: The GIL is no obstacle: Pillow's C codecs release it for much of the decode,
#: the resize and the encode, and where they do not, the interpreter switches
#: threads every few milliseconds, so the loop still gets its turns. Same
#: pattern as `_HASHING` in app/core/security.py.
_PROCESSING = asyncio.Semaphore(1)


def _prepare(data: bytes, declared_type: str | None) -> tuple[bytes, str]:
    image_format, extension = validate_image(data, declared_type)
    return shrink_to_fit(data, image_format), extension


async def prepare_upload(data: bytes, declared_type: str | None) -> tuple[bytes, str]:
    """Validate an upload and bring it to a sane size; returns `(bytes, extension)`.

    Stored at a sane size rather than at whatever the camera produced: a product
    photo straight off a phone is several megabytes and is rendered into a card a
    few hundred pixels wide, and the shopper paid for the difference on every
    page.

    Both steps share one semaphore hold and one thread hop, because
    `validate_image` parses the file too (`verify()`) and its pixel budget is what
    makes the decode in `shrink_to_fit` safe. A `ValidationError` raised in the
    thread propagates to the caller unchanged.
    """
    async with _PROCESSING:
        return await asyncio.to_thread(_prepare, data, declared_type)


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

    data, extension = await prepare_upload(data, declared_type)
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

    # The bucket first. If storage refuses, the row is untouched and the admin
    # can retry; the other order would leave a public file no row points to. A
    # later failure here leaves a row whose file is gone - a retry clears that,
    # since a missing object counts as deleted.
    await discard_objects(db, storage, [url])

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


async def discard_objects(db: AsyncSession, storage: StorageBackend, urls: Sequence[str]) -> None:
    """Delete the stored objects behind `urls`, keeping any an order still shows.

    Order items snapshot the image URL, so removing the object would turn a past
    order's thumbnail into a broken link. Those files stay; the rest go.
    """
    wanted = [url for url in urls if url]
    if not wanted:
        return

    referenced = set(
        (await db.scalars(select(OrderItem.image_url).where(OrderItem.image_url.in_(wanted)))).all()
    )
    for url in wanted:
        if url in referenced:
            continue
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
