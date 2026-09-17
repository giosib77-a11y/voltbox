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
from PIL import Image, JpegImagePlugin, UnidentifiedImageError

from app.core.config import settings
from app.core.errors import ValidationError

#: Only these three. SVG is deliberately absent: it is a document format that
#: can carry scripts, and it would be served from the same origin as the site.
ALLOWED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}

_MIB = 1024 * 1024

#: What one upload costs to verify, decode and shrink, as `(fixed, per pixel)`.
#:
#: Measured, not derived: `validate_image` + `shrink_to_fit` on one image per
#: case in a fresh process, Pillow 12.3, peak commit on Windows and peak RSS in
#: the production image, fitted over two sizes and rounded up. The audit that
#: asked for this limit assumed one number for every format - 50M pixels x 4
#: bytes, around 200 MB - where a WebP at that resolution actually peaks at
#: 812 MB. That spread is why the limit cannot be a single pixel count: it would
#: be either unsafe for a WebP or useless for a photo.
#:
#: Each pair is the most expensive variant of its path, because the ceiling is
#: set by the worst file the validation accepts, not by the average upload. The
#: fixed part is mostly the re-encode of the 1600px result, which is why WebP -
#: saved with `method=6` - carries most of it, and it is rounded up well past the
#: measurement on purpose: the peak does not grow smoothly with the pixel count.
#: Measured on Linux, a 2250x1688 WebP peaks 9 MiB above a 2190x1643 one, which
#: is the allocator handing out whole blocks. The margin lives in the fixed part
#: because that is where such a jump is largest relative to the total.
#:
#: The smallest limit any of these produces at the default budget is 2.62M
#: pixels, which is more than 1600x1600: an image already small enough to be
#: stored untouched is never refused, whatever its format. Measured at each of
#: these limits, the peak lands within 10% of the budget and under it.
DECODE_COST = {
    # Measured 6.47 B/px + 9.8 MB. The bitmap (4 bytes per pixel even for RGB),
    # reduce()'s half-size copy on the way to MAX_STORED_EDGE, and a coefficient
    # buffer. Admits 13.3 megapixels, which covers every phone's default photo.
    "JPEG": (11 * _MIB, 7),
    # Measured 12.03 B/px + 1.3 MB. Full-resolution chroma (4:4:4, 4:2:2) or
    # four components (CMYK) make that coefficient buffer two to four times
    # bigger. Cameras do not write these; image editors exporting at high
    # quality do.
    "JPEG_FULL_CHROMA": (3 * _MIB, 13),
    # Measured 8.98 B/px + 15.6 MB, the fixed part rounded up for the same
    # reason as WebP's. RGBA is the worst case: resize() premultiplies into a
    # second full-size copy (RGBa) and skips reduce() while both are alive.
    "PNG": (24 * _MIB, 9),
    # Measured 15.77 B/px + 38.6 MB, the fixed part carrying the margin above.
    # libwebp's animation decoder - the only WebP path Pillow has - holds a
    # current and a previous canvas, Pillow copies the frame out as `bytes`, and
    # only then fills its own bitmap. Three times a JPEG's pixel for the same
    # picture, which is why a WebP is held to 2.6 megapixels and a photo to 13.3.
    "WEBP": (60 * _MIB, 16),
}


def _decode_cost(probe: Image.Image, image_format: str) -> tuple[int, int]:
    """The `(fixed, per pixel)` cost of decoding this particular image.

    Everything read here comes from the header: `Image.open` parses the format,
    the mode and the JPEG sampling factors without materialising a pixel, which
    is what lets the cost be checked before anything is allocated.

    JPEG is split in two because a progressive file makes libjpeg hold every DCT
    coefficient of the image at once, and how much that is depends on the chroma
    sampling. A baseline single-scan file needs none of it, but the header cannot
    promise that a file is single-scan - the scan count is only known once the
    whole file has been read - so both classes are priced as if the buffer were
    there. Grayscale and 4:2:0 are the cheap class, and they are also what every
    phone camera writes.
    """
    if image_format != "JPEG":
        return DECODE_COST[image_format]
    subsampled = probe.mode == "L" or JpegImagePlugin.get_sampling(probe) == 2
    return DECODE_COST["JPEG" if subsampled else "JPEG_FULL_CHROMA"]


def _max_pixels(probe: Image.Image, image_format: str) -> int:
    """How many pixels of this image fit in the decode budget.

    Never negative: a budget below the fixed cost leaves room for nothing, and
    the answer is then zero rather than a negative limit that would accept
    everything.
    """
    fixed, per_pixel = _decode_cost(probe, image_format)
    return max(0, (settings.max_image_decode_bytes - fixed) // per_pixel)


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
    pixels, which is what makes the checks below meaningful before any
    allocation: both the resolution and what it will cost to decode are known
    while the bitmap still does not exist.
    """
    if not data:
        raise ValidationError("The file is empty", code="EMPTY_FILE")
    if len(data) > settings.max_image_bytes:
        limit_mb = settings.max_image_bytes // (1024 * 1024)
        raise ValidationError(
            f"The image must be at most {limit_mb} MB",
            code="IMAGE_TOO_LARGE",
            # The panel turns this into advice. A photo straight off a phone is
            # the ordinary way to meet this limit, and "too large" on its own
            # reads like the feature is broken.
            details={"maxBytes": settings.max_image_bytes},
        )

    try:
        with Image.open(io.BytesIO(data)) as probe:
            image_format = (probe.format or "").upper()
            width, height = probe.size
            # While the header is still open: verify() releases it, and the
            # sampling factors are only readable from the probe.
            allowed = image_format in ALLOWED_FORMATS
            pixel_budget = _max_pixels(probe, image_format) if allowed else 0
            probe.verify()
    except Image.DecompressionBombError as exc:
        # Pillow has a guard of its own: it warns above MAX_IMAGE_PIXELS
        # (89,478,485) and raises above twice that, inside open(), before the
        # size above is ever read. DecompressionBombError is a plain Exception -
        # not an OSError, not a ValueError - so it used to pass straight through
        # the handler below and reach the client as a 500 for an image that was
        # merely too big. The budget here is far stricter than Pillow's limit at
        # any sane setting, so the two guards now agree on the answer as well as
        # on the verdict.
        raise ValidationError(
            "The image resolution is too large", code="IMAGE_TOO_MANY_PIXELS"
        ) from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("This file is not a readable image", code="INVALID_IMAGE") from exc

    if not allowed:
        raise ValidationError(
            "Only JPEG, PNG and WebP images are accepted",
            code="UNSUPPORTED_IMAGE_FORMAT",
            details={"detected": image_format or "unknown", "declared": declared_type},
        )

    # A decompression bomb is small on disk and enormous once decoded, and the
    # decode is what allocates - so the limit is memory, converted into a pixel
    # count at this file's own cost. A WebP buys roughly a third of the pixels a
    # phone's JPEG does for the same memory.
    if width * height > pixel_budget:
        # The largest version of *this* image that would fit, so the panel can
        # name a size to export instead of only refusing one.
        scale = (pixel_budget / (width * height)) ** 0.5
        raise ValidationError(
            "The image resolution is too large",
            code="IMAGE_TOO_MANY_PIXELS",
            details={
                "width": width,
                "height": height,
                "maxWidth": max(1, int(width * scale)),
                "maxHeight": max(1, int(height * scale)),
            },
        )

    return image_format, ALLOWED_FORMATS[image_format]


#: The longest side an image is stored at.
#:
#: Nothing used to resize an upload: the bytes a phone camera produced were the
#: bytes a shopper downloaded into a 200-pixel card. Measured on a 12MP photo,
#: 2277 KB became 527 KB at this size - the same picture, four times cheaper on
#: a mobile connection, and the largest product image on screen is around 800px
#: wide even on a desktop.
MAX_STORED_EDGE = 1600

#: JPEG quality for a re-encode. 82 is the point where the file stops shrinking
#: much and the eye stops noticing.
JPEG_QUALITY = 82


def shrink_to_fit(data: bytes, image_format: str) -> bytes:
    """The same image with its longest side at most MAX_STORED_EDGE.

    Returns the original bytes untouched when it already fits. Re-encoding a
    small image would only lose quality, and a supplier's already-optimised
    photo is better left exactly as it arrived.

    The format is preserved rather than normalised to JPEG: a PNG product shot
    on a transparent background turns into one on a black background otherwise,
    which is a worse picture than a large one.
    """
    with Image.open(io.BytesIO(data)) as image:
        if max(image.size) <= MAX_STORED_EDGE:
            return data

        image.thumbnail((MAX_STORED_EDGE, MAX_STORED_EDGE), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        if image_format == "JPEG":
            image.convert("RGB").save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        elif image_format == "PNG":
            image.save(buffer, format="PNG", optimize=True)
        else:
            image.save(buffer, format="WEBP", quality=JPEG_QUALITY, method=6)
        shrunk = buffer.getvalue()

    # A re-encode that came out larger is not worth keeping - it happens with
    # small PNGs whose palette the resize expands.
    return shrunk if len(shrunk) < len(data) else data


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


#: Where the in-memory fake is an acceptable stand-in. Anywhere else, an
#: unconfigured bucket is a misconfiguration rather than a mode to run in.
LOCAL_ENVS = {"development", "test"}


def get_storage() -> StorageBackend:
    """The configured backend; the in-memory one only outside a deployment.

    Falling back rather than failing keeps the whole feature testable and lets
    the panel run locally before any bucket exists. It must not survive into a
    deployment: uploads would land in one worker's memory, the saved URL would
    point at `storage.test` (a reserved name that resolves nowhere), and the
    order items that snapshot that URL keep it forever. Nothing raises, so the
    panel reports success and the breakage only shows on the storefront.

    A test run never gets the real bucket, whatever the environment holds. The
    credentials are read from `.env`, and a developer's `.env` points at the
    live project - so anything that uploads without overriding this dependency
    writes into production storage while pointed at a local database. Those
    files are orphaned the moment they are written: no row here refers to them,
    nothing cleans them up, and they are indistinguishable from real ones
    afterwards except by size.
    """
    if settings.app_env == "test":
        return InMemoryStorage()

    if settings.supabase_project_ref and settings.supabase_service_role_key:
        return SupabaseStorage(
            settings.supabase_project_ref,
            settings.supabase_service_role_key,
            settings.supabase_storage_bucket,
        )

    if settings.app_env not in LOCAL_ENVS:
        raise RuntimeError(
            f"Object storage is not configured and APP_ENV is {settings.app_env!r}. "
            "Set SUPABASE_PROJECT_REF and SUPABASE_SERVICE_ROLE_KEY; without them "
            "uploaded images would be written to process memory and lost."
        )

    return InMemoryStorage()
