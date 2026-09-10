"""Object storage for product images.

What it does: defines the storage interface, a Supabase implementation and an
in-memory fake, plus the validation every upload must survive.
Where it fits: used by services/admin_image.py; the fake is what the test suite
runs against, so image handling is fully covered without credentials.

Why a public bucket: signed URLs expire. A storefront page would start showing
broken images, and worse, order items snapshot the image URL - an expired link
in a two-year-old order is not recoverable.
"""

from __future__ import annotations

import io
import uuid
from typing import Protocol

import httpx
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.errors import ValidationError

#: Only these three. SVG is deliberately absent: it is a document format that
#: can carry scripts, and it would be served from the same origin as the site.
ALLOWED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


class StorageBackend(Protocol):
    """What the image service needs from storage."""

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Store the object and return its public URL."""
        ...

    async def delete(self, key: str) -> None:
        """Remove the object. Missing objects are not an error."""
        ...


def validate_image(data: bytes, declared_type: str | None) -> tuple[str, str]:
    """Decode the bytes and return `(format_name, extension)`.

    The filename extension and the client-declared MIME type are both supplied
    by the caller and neither is evidence of anything, so the file is actually
    decoded. `Image.verify()` parses the structure without materialising the
    pixels, which is what makes the size check meaningful before any allocation.
    """
    if not data:
        raise ValidationError("The file is empty", code="EMPTY_FILE")
    if len(data) > settings.max_image_bytes:
        limit_mb = settings.max_image_bytes // (1024 * 1024)
        raise ValidationError(f"The image must be at most {limit_mb} MB", code="IMAGE_TOO_LARGE")

    try:
        with Image.open(io.BytesIO(data)) as probe:
            image_format = (probe.format or "").upper()
            width, height = probe.size
            probe.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("This file is not a readable image", code="INVALID_IMAGE") from exc

    if image_format not in ALLOWED_FORMATS:
        raise ValidationError(
            "Only JPEG, PNG and WebP images are accepted",
            code="UNSUPPORTED_IMAGE_FORMAT",
            details={"detected": image_format or "unknown", "declared": declared_type},
        )

    # A decompression bomb is small on disk and enormous once decoded; refusing
    # by pixel count is the only check that catches it.
    if width * height > settings.max_image_pixels:
        raise ValidationError("The image resolution is too large", code="IMAGE_TOO_MANY_PIXELS")

    return image_format, ALLOWED_FORMATS[image_format]


def object_key(product_id: uuid.UUID, extension: str) -> str:
    """`products/<product id>/<uuid>.<ext>` - never the uploaded filename.

    A caller-supplied name would carry path separators, unicode look-alikes and
    collisions into the bucket.
    """
    return f"products/{product_id}/{uuid.uuid4().hex}.{extension}"


class InMemoryStorage:
    """Test and offline backend. Keeps objects in a dict."""

    def __init__(self, base_url: str = "https://storage.test/voltbox") -> None:
        self.base_url = base_url.rstrip("/")
        self.objects: dict[str, bytes] = {}

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        self.objects[key] = data
        return f"{self.base_url}/{key}"

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def url_for(self, key: str) -> str:
        return f"{self.base_url}/{key}"


class SupabaseStorage:
    """Supabase Storage over its REST API.

    httpx rather than the supabase client: this needs two calls, and the client
    would pull in a much larger dependency for them.
    """

    def __init__(self, project_ref: str, service_key: str, bucket: str) -> None:
        self.base = f"https://{project_ref}.supabase.co/storage/v1"
        self.bucket = bucket
        self.headers = {
            "Authorization": f"Bearer {service_key}",
            # The service role key must never reach the browser; it lives only
            # in the backend process.
            "apikey": service_key,
        }

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base}/object/{self.bucket}/{key}",
                content=data,
                headers={**self.headers, "Content-Type": content_type, "x-upsert": "false"},
            )
        if response.status_code >= 400:
            raise ValidationError(
                "The image could not be stored",
                code="STORAGE_UPLOAD_FAILED",
                details={"status": response.status_code},
            )
        return f"{self.base}/object/public/{self.bucket}/{key}"

    async def delete(self, key: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            # A missing object is not an error: deletion has to be idempotent so
            # a retry after a timeout does not fail.
            await client.delete(f"{self.base}/object/{self.bucket}/{key}", headers=self.headers)


def get_storage() -> StorageBackend:
    """The configured backend, or the in-memory one when Supabase is not set up.

    Falling back rather than failing keeps the whole feature testable and lets
    the panel run locally before any bucket exists.
    """
    if settings.supabase_project_ref and settings.supabase_service_role_key:
        return SupabaseStorage(
            settings.supabase_project_ref,
            settings.supabase_service_role_key,
            settings.supabase_storage_bucket,
        )
    return InMemoryStorage()
