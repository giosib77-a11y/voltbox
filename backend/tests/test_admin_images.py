"""Product images.

What it covers: uploads are validated by decoding, not by trusting the filename
or the declared MIME type; the one-primary-per-product rule survives the order
in which SQLAlchemy flushes; and deleting an image never breaks the thumbnail of
a past order.

Runs against the in-memory storage backend, so image handling is fully covered
without Supabase credentials.
"""

import asyncio
import io
import math
import os
import struct
import subprocess
import sys
import threading
import time
import types
import uuid
import zlib
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager

import httpx
import pytest
from app.core.config import settings
from app.core.errors import AppError, ValidationError
from app.db.models import ROLE_ADMIN, OrderItem, ProductImage
from app.main import app
from app.services import admin_image
from app.services import storage as storage_module
from app.services.storage import (
    DECODE_COST,
    MAX_STORED_EDGE,
    InMemoryStorage,
    SupabaseStorage,
    get_storage,
    shrink_to_fit,
    validate_image,
)
from PIL import Image, ImageCms, ImageOps, PngImagePlugin, UnidentifiedImageError
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

ADMIN = "/api/v1/admin"


#: One flat colour per mode. Decode memory follows the dimensions and the
#: format, never the picture, so a solid image measures the same as a photograph.
COLOURS: dict[str, float | tuple[float, ...]] = {
    "RGB": (200, 40, 10),
    "RGBA": (200, 40, 10, 128),
    "CMYK": (10, 40, 200, 5),
    "L": 120,
}


def image_bytes(
    fmt: str = "PNG", size: tuple[int, int] = (32, 32), mode: str = "RGB", **options: object
) -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, COLOURS[mode]).save(buffer, format=fmt, **options)
    return buffer.getvalue()


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload))
    )


def header_only_png(width: int, height: int) -> bytes:
    """A PNG that declares a size and carries no picture.

    A real image of these dimensions cannot be built - that is the whole point of
    a decompression bomb - and `Image.open` only ever reads the header, so a few
    hand-written chunks are the honest way to present one.
    """
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(b""))
        + png_chunk(b"IEND", b"")
    )


#: An sRGB profile, 588 bytes: something real to carry through a re-encode.
ICC_PROFILE = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()

EXIF_ORIENTATION = 0x0112
EXIF_MAKE = 0x010F
EXIF_GPS_IFD = 0x8825


def exif_bytes(
    orientation: int | None = None, *, gps: bool = False, make: str | None = None
) -> bytes:
    """EXIF the way a phone writes it: orientation, the maker, and where it was."""
    exif = Image.Exif()
    if orientation is not None:
        exif[EXIF_ORIENTATION] = orientation
    if make is not None:
        exif[EXIF_MAKE] = make
    if gps:
        exif[EXIF_GPS_IFD] = {1: "N", 2: (41.0, 42.0, 0.0)}
    return exif.tobytes()


def patterned(size: tuple[int, int], mode: str = "RGB") -> Image.Image:
    """A picture whose every pixel differs from its neighbours.

    A flat colour decodes to the same bytes however it was damaged, so it cannot
    show that a strip left the pixels alone.
    """
    count = size[0] * size[1] * len(mode)
    return Image.frombytes(mode, size, (bytes(range(251)) * (count // 251 + 1))[:count])


def encode(image: Image.Image, fmt: str, **options: object) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **options)
    return buffer.getvalue()


def pixels(data: bytes) -> tuple[str, tuple[int, int], bytes]:
    """What a decoder makes of the file: mode, size and every pixel."""
    with Image.open(io.BytesIO(data)) as decoded:
        return decoded.mode, decoded.size, decoded.tobytes()


def jpeg_markers(data: bytes) -> list[int]:
    """The marker codes of a JPEG's header segments, up to and including SOS."""
    markers: list[int] = []
    pos = 2
    while True:
        assert data[pos] == 0xFF
        markers.append(data[pos + 1])
        if data[pos + 1] == 0xDA:
            return markers
        pos += 2 + int.from_bytes(data[pos + 2 : pos + 4], "big")


def jpeg_with_segments(jpeg: bytes, *segments: tuple[int, bytes], trailer: bytes = b"") -> bytes:
    """`jpeg` with extra header segments after SOI, and bytes after its EOI."""
    extra = b"".join(
        bytes((0xFF, marker)) + (len(payload) + 2).to_bytes(2, "big") + payload
        for marker, payload in segments
    )
    return jpeg[:2] + extra + jpeg[2:] + trailer


def png_chunk_types(data: bytes) -> list[bytes]:
    kinds: list[bytes] = []
    pos = 8
    while pos < len(data):
        kinds.append(data[pos + 4 : pos + 8])
        pos += 12 + int.from_bytes(data[pos : pos + 4], "big")
    return kinds


def webp_chunks(data: bytes) -> dict[bytes, bytes]:
    chunks: dict[bytes, bytes] = {}
    pos = 12
    while pos < len(data):
        length = int.from_bytes(data[pos + 4 : pos + 8], "little")
        chunks[data[pos : pos + 4]] = data[pos + 8 : pos + 8 + length]
        pos += 8 + length + length % 2
    return chunks


def only_object(storage: InMemoryStorage) -> bytes:
    (stored,) = storage.objects.values()
    return stored


@pytest.fixture
def storage() -> Generator[InMemoryStorage]:
    backend = InMemoryStorage()
    app.dependency_overrides[get_storage] = lambda: backend
    yield backend
    app.dependency_overrides.pop(get_storage, None)


@pytest.fixture
async def headers(db: AsyncSession) -> dict[str, str]:
    admin = await make_user(db, email="image-admin@voltbox.ge", role=ROLE_ADMIN)
    return auth_header(admin)


@pytest.fixture
async def product_id(db: AsyncSession) -> str:
    category = await make_category(db, slug="imaged")
    brand = await make_brand(db, "ImageBrand")
    product = await make_product(db, category, brand, slug="imaged-1")
    # The factory attaches images; start from a clean slate. A bulk DELETE, not
    # `for image in product.images` - the relationship is not loaded on a freshly
    # added object, so touching it would lazy-load and raise MissingGreenlet.
    await db.execute(delete(ProductImage).where(ProductImage.product_id == product.id))
    await db.flush()
    return str(product.id)


async def _upload(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    *,
    data: bytes | None = None,
    filename: str = "photo.png",
    content_type: str = "image/png",
) -> httpx.Response:
    return await client.post(
        f"{ADMIN}/products/{product_id}/images",
        headers=headers,
        files={"file": (filename, data or image_bytes(), content_type)},
    )


async def test_the_first_upload_becomes_the_primary_image(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str, storage: InMemoryStorage
) -> None:
    response = await _upload(client, headers, product_id)

    assert response.status_code == 201
    body = response.json()
    # A product must never be left without a primary image.
    assert body["isPrimary"] is True
    assert body["position"] == 0
    assert len(storage.objects) == 1
    # The stored key never contains the uploaded filename.
    (key,) = storage.objects
    assert key.startswith(f"products/{product_id}/")
    assert "photo" not in key


async def test_a_renamed_text_file_is_rejected(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str, storage: InMemoryStorage
) -> None:
    """The extension and the declared MIME type are both attacker-supplied."""
    response = await _upload(
        client, headers, product_id, data=b"just some text, definitely not a png"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IMAGE"
    assert storage.objects == {}


async def test_an_svg_is_rejected(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str
) -> None:
    """SVG can carry scripts and would be served from the site's own origin."""
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    response = await _upload(
        client, headers, product_id, data=svg, filename="x.svg", content_type="image/svg+xml"
    )

    assert response.status_code == 400


async def test_a_gif_is_rejected_even_though_it_decodes(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str
) -> None:
    response = await _upload(client, headers, product_id, data=image_bytes("GIF"))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_IMAGE_FORMAT"


#: Formats Pillow can open that are not ours, one per plugin that has had
#: vulnerabilities in its parser. Each needs a Pillow writer, so the bytes are
#: real files and not hand-made headers.
FOREIGN_FORMATS = ["GIF", "TIFF", "BMP", "PPM", "EPS"]


def _forbid_parser(monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    """Make the format's parser blow up with something `validate_image` does not catch.

    `_open` is the plugin's parser: `Image.open` calls it only once the file's
    signature matched the plugin. A RuntimeError is neither a decode failure nor
    an `OSError`, so reaching the parser turns into a 500 instead of a refusal.
    """
    Image.init()
    factory = Image.OPEN[fmt][0]

    def reached(self: object) -> None:
        raise RuntimeError(f"the {fmt} parser was handed an upload")

    monkeypatch.setattr(factory, "_open", reached)


@pytest.mark.parametrize("fmt", FOREIGN_FORMATS)
async def test_a_format_we_do_not_accept_is_never_parsed(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    storage: InMemoryStorage,
    monkeypatch: pytest.MonkeyPatch,
    fmt: str,
) -> None:
    """Pillow's other parsers are attack surface for a file we refuse anyway.

    The refusal still names the format, which is what lets the panel tell the
    admin what to export instead of calling the file broken.
    """
    data = image_bytes(fmt)
    _forbid_parser(monkeypatch, fmt)

    response = await _upload(client, headers, product_id, data=data)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "UNSUPPORTED_IMAGE_FORMAT"
    assert error["details"]["detected"] == fmt
    assert storage.objects == {}


def test_shrink_to_fit_opens_only_the_format_it_was_validated_as(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second `Image.open` is restricted too, not just the validating one."""
    gif = image_bytes("GIF")
    _forbid_parser(monkeypatch, "GIF")

    with pytest.raises(UnidentifiedImageError):
        shrink_to_fit(gif, "PNG")


@pytest.mark.parametrize(
    "data",
    [
        b"\xff\xd8\xff\xe0" + b"\x00" * 12,
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 8,
        b"RIFF\x00\x00\x00\x00WEBP",
    ],
    ids=["jpeg", "png", "webp"],
)
async def test_a_damaged_file_of_an_allowed_format_is_not_called_another_format(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str, data: bytes
) -> None:
    """MPO shares JPEG's signature: a signature match is not the same as 'foreign'."""
    response = await _upload(client, headers, product_id, data=data)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


#: The first box of an iPhone photo, and of an HEIC whose major brand is the
#: generic HEIF one. Pillow cannot read past either.
HEIC_HEADERS = {
    "iphone": b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic",
    "generic-major-brand": b"\x00\x00\x00\x18ftypmif1\x00\x00\x00\x00mif1heic",
}


@pytest.mark.parametrize("header", HEIC_HEADERS.values(), ids=HEIC_HEADERS.keys())
async def test_a_heic_is_refused_as_a_format_not_as_a_non_image(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str, header: bytes
) -> None:
    """The panel can only tell the admin what to change if it is told the format."""
    response = await _upload(
        client,
        headers,
        product_id,
        data=header + b"\x00\x00\x00\x08free",
        filename="IMG_0001.HEIC",
        content_type="image/heic",
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "UNSUPPORTED_IMAGE_FORMAT"
    assert error["details"] == {"detected": "HEIC", "declared": "image/heic"}


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
async def test_the_three_allowed_formats_are_accepted(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str, fmt: str
) -> None:
    response = await _upload(client, headers, product_id, data=image_bytes(fmt))

    assert response.status_code == 201


async def test_setting_a_new_primary_unsets_the_old_one(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str, db: AsyncSession
) -> None:
    first = (await _upload(client, headers, product_id)).json()
    second = (await _upload(client, headers, product_id)).json()
    assert first["isPrimary"] is True

    response = await client.post(
        f"{ADMIN}/products/{product_id}/images/{second['id']}/primary", headers=headers
    )

    assert response.status_code == 200
    flags = {image["id"]: image["isPrimary"] for image in response.json()}
    assert flags[second["id"]] is True
    assert flags[first["id"]] is False

    # The partial unique index is the real guarantee; assert the database agrees.
    primaries = await db.scalars(
        select(ProductImage).where(
            ProductImage.product_id == uuid.UUID(product_id), ProductImage.is_primary.is_(True)
        )
    )
    assert len(list(primaries)) == 1


async def test_reorder_requires_the_complete_list(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str
) -> None:
    first = (await _upload(client, headers, product_id)).json()
    await _upload(client, headers, product_id)

    partial = await client.put(
        f"{ADMIN}/products/{product_id}/images/order",
        headers=headers,
        json={"imageIds": [first["id"]]},
    )

    # A partial list would leave the rest at stale positions and the final order
    # would come from the id tiebreaker rather than from intent.
    assert partial.status_code == 400
    assert partial.json()["error"]["code"] == "INCOMPLETE_IMAGE_ORDER"


async def test_reorder_applies_the_given_order(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str
) -> None:
    first = (await _upload(client, headers, product_id)).json()
    second = (await _upload(client, headers, product_id)).json()
    third = (await _upload(client, headers, product_id)).json()

    response = await client.put(
        f"{ADMIN}/products/{product_id}/images/order",
        headers=headers,
        json={"imageIds": [third["id"], first["id"], second["id"]]},
    )

    assert response.status_code == 200
    assert [image["id"] for image in response.json()] == [
        third["id"],
        first["id"],
        second["id"],
    ]
    assert [image["position"] for image in response.json()] == [0, 1, 2]


async def test_deleting_the_primary_promotes_the_next_one(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str, storage: InMemoryStorage
) -> None:
    first = (await _upload(client, headers, product_id)).json()
    second = (await _upload(client, headers, product_id)).json()

    response = await client.delete(
        f"{ADMIN}/products/{product_id}/images/{first['id']}", headers=headers
    )

    assert response.status_code == 204
    remaining = await client.get(f"{ADMIN}/products/{product_id}", headers=headers)
    images = remaining.json()["images"]
    assert [image["id"] for image in images] == [second["id"]]
    # A product with images always has a primary one.
    assert images[0]["isPrimary"] is True
    assert images[0]["position"] == 0
    # The object is gone from storage too, since nothing references it.
    assert len(storage.objects) == 1


async def test_an_image_referenced_by_an_order_is_kept_in_storage(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    storage: InMemoryStorage,
    db: AsyncSession,
) -> None:
    """Order items snapshot the URL; deleting the file would break history."""
    from app.services import order as order_service

    uploaded = (await _upload(client, headers, product_id)).json()
    await order_service.create_order(
        db,
        items=[(uuid.UUID(product_id), 1)],
        customer={"phone": "555123456", "city": "თბილისი", "address": "ქუჩა 1"},
        payment_method="cash",
        user=None,
    )
    snapshot = await db.scalar(select(OrderItem.image_url))
    assert snapshot == uploaded["url"]

    response = await client.delete(
        f"{ADMIN}/products/{product_id}/images/{uploaded['id']}", headers=headers
    )

    assert response.status_code == 204
    # The row is gone, but the object stays: a two-year-old order must still
    # render its thumbnail.
    assert len(storage.objects) == 1


async def test_upload_rejects_a_file_that_is_too_large(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_image_bytes", 100)

    response = await _upload(client, headers, product_id, data=image_bytes(size=(200, 200)))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IMAGE_TOO_LARGE"
    # The panel needs the limit to say what to do about it; a photo off a phone
    # is the ordinary way to meet this one.
    assert response.json()["error"]["details"]["maxBytes"] == 100


async def test_upload_rejects_a_decompression_bomb_by_its_decode_cost(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    # A small file can decode to an enormous bitmap, and the decode is what
    # allocates - so the budget is memory, checked before anything is decoded.
    # The image has to be over MAX_STORED_EDGE, because that is the only path
    # that decodes at all: a flat 2000x2000 PNG is a few kilobytes on disk and a
    # 16 MB bitmap once opened, which is the whole shape of the attack.
    monkeypatch.setattr(settings, "max_image_decode_bytes", 100)

    response = await _upload(client, headers, product_id, data=image_bytes("PNG", (2000, 2000)))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IMAGE_TOO_MANY_PIXELS"


async def test_uploading_to_a_missing_product_is_404(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    response = await _upload(client, headers, str(uuid.uuid4()))

    assert response.status_code == 404


async def test_deleting_a_product_takes_its_stored_objects_with_it(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    storage: InMemoryStorage,
) -> None:
    """Deleting the product must not leave files behind in the bucket.

    Nothing ever points at them again, so they would be invisible cost forever.
    """
    await _upload(client, headers, product_id)
    await _upload(client, headers, product_id, filename="second.png")
    assert len(storage.objects) == 2

    response = await client.delete(f"{ADMIN}/products/{product_id}", headers=headers)

    assert response.status_code == 204
    assert storage.objects == {}


class TestStorageSelection:
    """`get_storage` must not hand a deployment the in-memory fake.

    The fake keeps objects in one worker's dict and hands back a
    `https://storage.test/...` URL. Nothing raises, so an admin upload reports
    success while the file is unreachable from the other worker, gone on the
    next restart, and frozen into any order item that snapshots the URL.
    """

    def test_uses_supabase_when_it_is_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "supabase_project_ref", "somewhere", raising=False)
        monkeypatch.setattr(
            settings, "supabase_service_role_key", SecretStr("a-key"), raising=False
        )
        monkeypatch.setattr(settings, "app_env", "production", raising=False)

        assert isinstance(get_storage(), SupabaseStorage)

    @pytest.mark.parametrize("env", ["development", "test"])
    def test_falls_back_locally(self, monkeypatch: pytest.MonkeyPatch, env: str) -> None:
        monkeypatch.setattr(settings, "supabase_project_ref", "", raising=False)
        monkeypatch.setattr(settings, "supabase_service_role_key", SecretStr(""), raising=False)
        monkeypatch.setattr(settings, "app_env", env, raising=False)

        assert isinstance(get_storage(), InMemoryStorage)

    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_refuses_to_fall_back_in_a_deployment(
        self, monkeypatch: pytest.MonkeyPatch, env: str
    ) -> None:
        monkeypatch.setattr(settings, "supabase_project_ref", "", raising=False)
        monkeypatch.setattr(settings, "supabase_service_role_key", SecretStr(""), raising=False)
        monkeypatch.setattr(settings, "app_env", env, raising=False)

        with pytest.raises(RuntimeError, match="Object storage is not configured"):
            get_storage()

    def test_refuses_when_only_half_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ref without a key is the shape a half-filled .env actually has."""
        monkeypatch.setattr(settings, "supabase_project_ref", "somewhere", raising=False)
        monkeypatch.setattr(settings, "supabase_service_role_key", SecretStr(""), raising=False)
        monkeypatch.setattr(settings, "app_env", "production", raising=False)

        with pytest.raises(RuntimeError, match="Object storage is not configured"):
            get_storage()

    def test_a_test_run_never_reaches_the_real_bucket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Credentials come from `.env`, which points at the live project.

        Anything that uploads without overriding this dependency - a script, a
        new test that forgets the fixture - writes into production storage while
        its database is local. The files are orphaned as they are written: no
        row refers to them, nothing collects them, and afterwards they look like
        real ones.
        """
        monkeypatch.setattr(settings, "supabase_project_ref", "a-real-project", raising=False)
        monkeypatch.setattr(
            settings, "supabase_service_role_key", SecretStr("a-real-key"), raising=False
        )
        monkeypatch.setattr(settings, "app_env", "test", raising=False)

        assert isinstance(get_storage(), InMemoryStorage)

    def test_development_still_uses_the_configured_bucket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Uploading real product images locally is the point of configuring it."""
        monkeypatch.setattr(settings, "supabase_project_ref", "a-real-project", raising=False)
        monkeypatch.setattr(
            settings, "supabase_service_role_key", SecretStr("a-real-key"), raising=False
        )
        monkeypatch.setattr(settings, "app_env", "development", raising=False)

        assert isinstance(get_storage(), SupabaseStorage)


class TestAnUploadIsStoredAtASaneSize:
    """Nothing used to resize an upload.

    The bytes a phone camera produced were the bytes a shopper downloaded into a
    card a few hundred pixels wide. Measured on a 12MP photo: 2277 KB stored,
    527 KB after this - the same picture, four times cheaper on a mobile
    connection, and larger than anything the site ever renders.
    """

    async def test_a_large_photo_is_shrunk(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
    ) -> None:
        big = image_bytes("JPEG", (4032, 3024))

        response = await client.post(
            f"/api/v1/admin/products/{product_id}/images",
            headers=headers,
            files={"file": ("photo.jpg", big, "image/jpeg")},
        )

        assert response.status_code == 201
        stored = next(iter(storage.objects.values()))
        with Image.open(io.BytesIO(stored)) as saved:
            assert max(saved.size) == MAX_STORED_EDGE
        assert len(stored) < len(big)

    async def test_an_image_that_already_fits_is_left_alone(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
    ) -> None:
        """Re-encoding a small image only loses quality. This one has no metadata
        to strip, so it comes back byte for byte (see
        TestWhatAPhotoKnowsDoesNotReachThePublicBucket for one that has)."""
        small = image_bytes("JPEG", (800, 600))

        await client.post(
            f"/api/v1/admin/products/{product_id}/images",
            headers=headers,
            files={"file": ("photo.jpg", small, "image/jpeg")},
        )

        assert next(iter(storage.objects.values())) == small

    async def test_a_png_stays_a_png(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
    ) -> None:
        """Normalising to JPEG would put a black background behind a product
        shot that was cut out on transparency."""
        await client.post(
            f"/api/v1/admin/products/{product_id}/images",
            headers=headers,
            files={"file": ("photo.png", image_bytes("PNG", (2400, 2400)), "image/png")},
        )

        stored = next(iter(storage.objects.values()))
        with Image.open(io.BytesIO(stored)) as saved:
            assert saved.format == "PNG"
            assert max(saved.size) == MAX_STORED_EDGE

    def test_the_shrink_keeps_the_aspect_ratio(self) -> None:
        wide = image_bytes("JPEG", (4000, 1000))

        with Image.open(io.BytesIO(shrink_to_fit(wide, "JPEG"))) as saved:
            assert saved.size == (MAX_STORED_EDGE, MAX_STORED_EDGE // 4)

    def test_a_re_encode_that_grew_is_discarded(self) -> None:
        """Some small PNGs come out larger after a resize; the original wins."""
        already_small = image_bytes("PNG", (100, 100))

        assert shrink_to_fit(already_small, "PNG") == already_small

    def test_a_png_is_not_saved_with_optimize(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`optimize=True` made a 2800x2100 PNG take 6.5 s of CPU instead of 0.5 s,
        for a file about 10% smaller. A worker serves nothing else meanwhile."""
        big = image_bytes("PNG", (2400, 2400))
        saves: list[dict[str, object]] = []
        real_save = Image.Image.save

        def spy(self: Image.Image, fp: object, format: str | None = None, **params: object) -> None:
            saves.append({"format": format, **params})
            real_save(self, fp, format=format, **params)  # type: ignore[arg-type]

        monkeypatch.setattr(Image.Image, "save", spy)

        shrink_to_fit(big, "PNG")

        assert [save["format"] for save in saves] == ["PNG"]
        assert not saves[0].get("optimize")


DROPPED_PNG_CHUNKS = [b"eXIf", b"tEXt", b"zTXt", b"iTXt", b"tIME"]


class TestWhatAPhotoKnowsDoesNotReachThePublicBucket:
    """A phone writes where a photo was taken, and with what, into the file.

    The bucket is public, so an upload kept as it arrived published that. The
    same EXIF block carries the orientation: a photo taken in portrait is stored
    as landscape pixels with a tag saying "turn me", and the resize used to drop
    the tag and keep the pixels, so it showed sideways on the site.
    """

    async def _store(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
        data: bytes,
        fmt: str = "jpeg",
    ) -> bytes:
        response = await _upload(
            client,
            headers,
            product_id,
            data=data,
            filename=f"photo.{fmt}",
            content_type=f"image/{fmt}",
        )
        assert response.status_code == 201, response.text
        return only_object(storage)

    async def test_a_portrait_phone_photo_is_stored_upright(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
    ) -> None:
        """4000x3000 with Orientation 6 is a 3000x4000 portrait on the phone."""
        photo = image_bytes("JPEG", (4000, 3000), exif=exif_bytes(6))

        stored = await self._store(client, headers, storage, product_id, photo)

        with Image.open(io.BytesIO(stored)) as saved:
            assert saved.size == (1200, 1600)
            assert EXIF_ORIENTATION not in saved.getexif()
            assert "exif" not in saved.info

    @pytest.mark.parametrize("progressive", [False, True])
    async def test_a_small_photo_loses_its_gps_and_device_without_a_re_encode(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
        progressive: bool,
    ) -> None:
        """It fits, so it used to come back byte for byte - GPS and all.

        Lossless: the pixels must decode identically, and the colour profile has
        to survive. Progressive too, because the walk has to follow the file scan
        by scan rather than look for the first EOI-shaped bytes.
        """
        original = encode(
            patterned((1200, 900)),
            "JPEG",
            exif=exif_bytes(gps=True, make="Acme"),
            icc_profile=ICC_PROFILE,
            progressive=progressive,
        )
        assert 0xE1 in jpeg_markers(original)

        stored = await self._store(client, headers, storage, product_id, original)

        markers = jpeg_markers(stored)
        assert 0xE1 not in markers  # APP1: EXIF and XMP
        assert 0xE2 in markers  # APP2: the ICC profile
        assert b"Acme" not in stored
        with Image.open(io.BytesIO(stored)) as saved:
            exif = saved.getexif()
            assert not exif.get_ifd(EXIF_GPS_IFD)
            assert EXIF_MAKE not in exif
            assert saved.info["icc_profile"] == ICC_PROFILE
        assert pixels(stored) == pixels(original)
        assert len(stored) < len(original)

    async def test_a_small_photo_in_portrait_is_turned_upright(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
    ) -> None:
        """It fits, so before this it was returned as it came, still needing the
        tag. The tag is metadata and goes, so the picture has to be turned.

        Orientation 6 means "rotate 90 degrees clockwise to view": the left half,
        red, ends up on top.
        """
        picture = Image.new("RGB", (1200, 900), (255, 0, 0))
        picture.paste((0, 0, 255), (600, 0, 1200, 900))
        photo = encode(
            picture, "JPEG", exif=exif_bytes(6, gps=True, make="Acme"), icc_profile=ICC_PROFILE
        )

        stored = await self._store(client, headers, storage, product_id, photo)

        with Image.open(io.BytesIO(stored)) as saved:
            assert saved.size == (900, 1200)
            exif = saved.getexif()
            assert EXIF_ORIENTATION not in exif
            assert not exif.get_ifd(EXIF_GPS_IFD)
            assert saved.info["icc_profile"] == ICC_PROFILE
            rgb = saved.convert("RGB")
            top = rgb.getpixel((450, 100))
            bottom = rgb.getpixel((450, 1100))
        assert isinstance(top, tuple)
        assert isinstance(bottom, tuple)
        assert top[0] > 200 > top[2]
        assert bottom[2] > 200 > bottom[0]

    @pytest.mark.parametrize("orientation", range(2, 9))
    def test_every_orientation_is_undone_exactly(self, orientation: int) -> None:
        """Against Pillow's own `exif_transpose`, in a format that loses nothing,
        so any difference is the rotation and not the codec."""
        source = encode(patterned((60, 40)), "PNG", exif=exif_bytes(orientation))
        with Image.open(io.BytesIO(source)) as opened:
            expected = ImageOps.exif_transpose(opened)
            assert expected is not None
            assert expected.size == ((40, 60) if orientation >= 5 else (60, 40))

        stored = shrink_to_fit(source, "PNG")

        assert pixels(stored) == ("RGB", expected.size, expected.tobytes())
        assert png_chunk_types(stored).count(b"eXIf") == 0

    async def test_a_png_loses_every_chunk_that_carries_metadata(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
    ) -> None:
        text = PngImagePlugin.PngInfo()
        text.add_text("Author", "Jane Doe")  # tEXt
        text.add_text("Comment", "secret note", zip=True)  # zTXt
        text.add_itxt("Title", "secret title", zip=True)  # iTXt
        written = encode(
            patterned((120, 80)),
            "PNG",
            pnginfo=text,
            exif=exif_bytes(gps=True, make="Acme"),
            icc_profile=ICC_PROFILE,
        )
        # tIME, which Pillow does not write, and a trailer after IEND.
        modified = png_chunk(b"tIME", struct.pack(">HBBBBB", 2024, 1, 2, 3, 4, 5))
        original = written[:-12] + modified + written[-12:] + b"TRAILER-SECRET"
        for kind in DROPPED_PNG_CHUNKS:
            assert kind in png_chunk_types(original), kind

        stored = await self._store(client, headers, storage, product_id, original, "png")

        kinds = png_chunk_types(stored)
        assert not set(DROPPED_PNG_CHUNKS) & set(kinds)
        assert b"iCCP" in kinds
        assert kinds[-1] == b"IEND"
        for secret in (b"Jane Doe", b"Acme", b"TRAILER-SECRET"):
            assert secret not in stored
        assert pixels(stored) == pixels(original)

    async def test_a_webp_loses_its_exif_and_xmp_and_keeps_its_profile(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
    ) -> None:
        original = encode(
            patterned((200, 100)),
            "WEBP",
            lossless=True,
            exif=exif_bytes(gps=True, make="Acme"),
            xmp=b"<x:xmpmeta>secret</x:xmpmeta>",
            icc_profile=ICC_PROFILE,
        )
        before = webp_chunks(original)
        assert {b"EXIF", b"XMP ", b"ICCP"} <= before.keys()
        assert before[b"VP8X"][0] & 0x0C == 0x0C

        stored = await self._store(client, headers, storage, product_id, original, "webp")

        after = webp_chunks(stored)
        assert b"EXIF" not in after
        assert b"XMP " not in after
        assert after[b"ICCP"] == ICC_PROFILE
        # EXIF and XMP flags cleared, the ICC flag (0x20) untouched.
        assert after[b"VP8X"][0] & 0x0C == 0
        assert after[b"VP8X"][0] & 0x20 == before[b"VP8X"][0] & 0x20 != 0
        assert int.from_bytes(stored[4:8], "little") == len(stored) - 8
        assert b"Acme" not in stored
        assert pixels(stored) == pixels(original)

    @pytest.mark.parametrize(
        ("fmt", "size"), [("JPEG", (2400, 1800)), ("PNG", (2000, 1000)), ("WEBP", (1700, 1000))]
    )
    def test_a_re_encode_keeps_the_colour_profile(self, fmt: str, size: tuple[int, int]) -> None:
        """Pillow's JPEG and WebP writers drop it unless it is handed over, and a
        wide-gamut photo then comes out duller than the one that was uploaded."""
        original = image_bytes(fmt, size, icc_profile=ICC_PROFILE, exif=exif_bytes(gps=True))

        stored = shrink_to_fit(original, fmt)

        with Image.open(io.BytesIO(stored)) as saved:
            assert max(saved.size) == MAX_STORED_EDGE
            assert saved.info["icc_profile"] == ICC_PROFILE
            assert "exif" not in saved.info

    def test_a_cmyk_profile_is_not_put_on_the_rgb_it_becomes(self) -> None:
        """A JPEG re-encode is RGB. A profile that describes CMYK would make a
        browser colour those pixels wrongly, so it is the one thing dropped."""
        cmyk_profile = ICC_PROFILE[:16] + b"CMYK" + ICC_PROFILE[20:]
        original = image_bytes("JPEG", (2400, 1800), mode="CMYK", icc_profile=cmyk_profile)

        stored = shrink_to_fit(original, "JPEG")

        with Image.open(io.BytesIO(stored)) as saved:
            assert saved.mode == "RGB"
            assert "icc_profile" not in saved.info

    async def test_comments_iptc_and_a_trailer_after_the_image_are_removed(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
    ) -> None:
        """APP13 is where Photoshop and press agencies put names and captions; a
        Samsung phone appends its own block after the EOI."""
        original = jpeg_with_segments(
            encode(patterned((300, 200)), "JPEG", icc_profile=ICC_PROFILE),
            (0xED, b"Photoshop 3.0\x00" + b"8BIM caption-secret"),
            (0xFE, b"comment-secret"),
            (0xE1, b"http://ns.adobe.com/xmp/extension/\x00xmp-secret"),
            trailer=b"TRAILER-SECRET",
        )

        stored = await self._store(client, headers, storage, product_id, original)

        for secret in (
            b"Photoshop",
            b"caption-secret",
            b"comment-secret",
            b"xmp-secret",
            b"TRAILER",
        ):
            assert secret not in stored
        assert stored.endswith(b"\xff\xd9")
        assert jpeg_markers(stored).count(0xE2) == 1
        assert pixels(stored) == pixels(original)

    def test_a_large_jpeg_does_not_carry_its_comment_into_the_re_encode(self) -> None:
        """Pillow's JPEG writer copies the source's COM segment unless told not to."""
        original = jpeg_with_segments(
            encode(patterned((2000, 1500)), "JPEG"), (0xFE, b"comment-secret")
        )

        assert b"comment-secret" in original
        assert b"comment-secret" not in shrink_to_fit(original, "JPEG")

    def test_adobe_colour_information_survives_the_strip(self) -> None:
        """APP14 says how to read a CMYK file's channels; without it the colours
        invert."""
        original = encode(patterned((200, 100), "CMYK"), "JPEG", exif=exif_bytes(gps=True))
        assert {0xE1, 0xEE} <= set(jpeg_markers(original))

        stored = shrink_to_fit(original, "JPEG")

        assert 0xE1 not in jpeg_markers(stored)
        assert 0xEE in jpeg_markers(stored)
        assert pixels(stored) == pixels(original)

    @pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
    def test_a_file_with_nothing_to_strip_is_stored_byte_for_byte(self, fmt: str) -> None:
        clean = encode(patterned((64, 48)), fmt)

        assert shrink_to_fit(clean, fmt) == clean

    @pytest.mark.parametrize("value", [0, 9, 65535])
    def test_an_orientation_that_is_not_a_rotation_is_not_one(self, value: int) -> None:
        """Only 2..8 are rotations. Anything else is a damaged tag: the picture is
        left as drawn, losslessly, and the tag goes with the rest of the EXIF."""
        original = encode(patterned((400, 300)), "JPEG", exif=exif_bytes(value, make="Acme"))

        stored = shrink_to_fit(original, "JPEG")

        assert b"Acme" not in stored
        assert pixels(stored) == pixels(original)

    def test_damaged_exif_is_dropped_not_a_500(self) -> None:
        original = jpeg_with_segments(
            encode(patterned((400, 300)), "JPEG"), (0xE1, b"Exif\x00\x00not a tiff header at all")
        )
        assert validate_image(original, "image/jpeg") == ("JPEG", "jpg")

        stored = shrink_to_fit(original, "JPEG")

        assert 0xE1 not in jpeg_markers(stored)
        assert pixels(stored) == pixels(original)

    def test_padding_between_jpeg_segments_is_skipped_not_refused(self) -> None:
        """Stray bytes between segments are junk, not a broken structure: the walk
        steps over them and does not copy them. (Called directly: Pillow's own
        `open` is stricter about where it tolerates them than the walk is.)"""
        clean = encode(patterned((400, 300)), "JPEG")
        padded = clean[:2] + b"\x00\x00\xff\xff" + clean[2:]

        assert storage_module._STRIP_METADATA["JPEG"](padded) == clean

    def test_a_webp_that_must_be_turned_is_costed_like_one_that_is_resized(self) -> None:
        """A 1600x1600 WebP is never decoded and costs 4.9 MiB. With Orientation 6
        it is decoded to be turned, and 2.56 megapixels of WebP is over the budget
        - measured, a 1601x1599 one peaks at 120.6 MiB."""
        assert validate_image(image_bytes("WEBP", (1600, 1600)), None)[0] == "WEBP"

        with pytest.raises(ValidationError) as refused:
            validate_image(image_bytes("WEBP", (1600, 1600), exif=exif_bytes(6)), None)

        assert refused.value.code == "IMAGE_TOO_MANY_PIXELS"

    @pytest.mark.parametrize("fmt", ["JPEG", "PNG"])
    def test_a_jpeg_or_png_at_the_edge_that_must_be_turned_still_fits_the_budget(
        self, fmt: str
    ) -> None:
        """Their budgets are above 1600x1600, so the rule costs them nothing."""
        turned = image_bytes(fmt, (1600, 1600), exif=exif_bytes(6))

        assert validate_image(turned, None)[0] == fmt

    @pytest.mark.parametrize(
        ("fmt", "broken"),
        [
            ("JPEG", "length past the end"),
            ("JPEG", "no EOI"),
            ("JPEG", "no scan"),
            ("JPEG", "not a JPEG"),
            ("PNG", "length past the end"),
            ("PNG", "no IEND"),
            ("PNG", "not a PNG"),
            ("WEBP", "RIFF size past the end"),
            ("WEBP", "chunk size past the end"),
            ("WEBP", "not a WebP"),
        ],
    )
    def test_a_container_that_cannot_be_walked_is_invalid_not_decoded(
        self, fmt: str, broken: str
    ) -> None:
        good = {
            "JPEG": encode(patterned((64, 48)), "JPEG"),
            "PNG": encode(patterned((16, 16)), "PNG"),
            "WEBP": encode(patterned((16, 16)), "WEBP", lossless=True),
        }[fmt]
        damaged = {
            ("JPEG", "length past the end"): good[:2] + b"\xff\xe1\xff\xff" + good[2:],
            ("JPEG", "no EOI"): good[:-2],
            ("JPEG", "no scan"): b"\xff\xd8\xff\xd9",
            ("JPEG", "not a JPEG"): b"nope",
            ("PNG", "length past the end"): good[:8] + b"\x00\xff\xff\xff" + good[12:],
            ("PNG", "no IEND"): good[:-12],
            ("PNG", "not a PNG"): b"nope",
            ("WEBP", "RIFF size past the end"): good[:4]
            + (len(good) + 92).to_bytes(4, "little")
            + good[8:],
            ("WEBP", "chunk size past the end"): good[:16] + b"\xff\xff\xff\x7f" + good[20:],
            ("WEBP", "not a WebP"): b"nope",
        }[(fmt, broken)]

        with pytest.raises(ValidationError) as refused:
            storage_module._STRIP_METADATA[fmt](damaged)

        assert refused.value.code == "INVALID_IMAGE"

    def test_a_small_jpeg_with_no_eoi_is_refused_not_decoded(self) -> None:
        """At or below the edge a decode would be unbudgeted, so there is no
        fallback to one."""
        original = encode(patterned((400, 300)), "JPEG")[:-2]

        with pytest.raises(ValidationError) as refused:
            shrink_to_fit(original, "JPEG")

        assert refused.value.code == "INVALID_IMAGE"


@asynccontextmanager
async def _loop_ticks() -> AsyncGenerator[Callable[[], int]]:
    """Count how often the event loop got to run a 5 ms timer inside the block."""
    count = 0

    async def ticker() -> None:
        nonlocal count
        while True:
            await asyncio.sleep(0.005)
            count += 1

    task = asyncio.create_task(ticker())
    try:
        yield lambda: count
    finally:
        task.cancel()


class TestUploadProcessingRunsOffTheEventLoop:
    """Decoding and re-encoding is seconds of CPU. On the event loop it stalled
    every other request, and under gunicorn's timeout it killed the worker."""

    @staticmethod
    def _spy(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, bytes, int]]:
        """Record `(step, data, thread id)` for each call, holding each for 50 ms
        so that work which is not serialised visibly overlaps."""
        events: list[tuple[str, bytes, int]] = []

        def validate(data: bytes, declared_type: str | None) -> tuple[str, str]:
            events.append(("validate", data, threading.get_ident()))
            time.sleep(0.05)
            return validate_image(data, declared_type)

        def shrink(data: bytes, image_format: str) -> bytes:
            events.append(("shrink", data, threading.get_ident()))
            time.sleep(0.05)
            return shrink_to_fit(data, image_format)

        monkeypatch.setattr(admin_image, "validate_image", validate)
        monkeypatch.setattr(admin_image, "shrink_to_fit", shrink)
        return events

    async def test_validate_and_shrink_run_on_a_worker_thread(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        events = self._spy(monkeypatch)

        response = await _upload(client, headers, product_id, data=image_bytes("PNG", (1700, 40)))

        assert response.status_code == 201
        assert [step for step, _, _ in events] == ["validate", "shrink"]
        loop_thread = threading.get_ident()
        assert all(thread != loop_thread for _, _, thread in events)

    async def test_the_loop_keeps_serving_while_an_image_is_processed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same fact seen from the other side: something else gets to run."""
        self._spy(monkeypatch)
        data = image_bytes("PNG", (1700, 40))

        async with _loop_ticks() as ticks:
            await admin_image.prepare_upload(data, "image/png")

        assert ticks() >= 3

    async def test_two_uploads_are_never_processed_at_the_same_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The semaphore is what keeps one decode per worker, so the memory ceiling
        stays MAX_IMAGE_DECODE_BYTES however many uploads arrive. A validate and a
        shrink are one job: another upload must not slip in between them.

        The ticks make the test about threads: processing that blocked the loop
        would be serialised too, trivially, and would not show whether the
        semaphore is what does it."""
        events = self._spy(monkeypatch)
        first, second = image_bytes("PNG", (1700, 40)), image_bytes("PNG", (1700, 41))

        async with _loop_ticks() as ticks:
            results = await asyncio.gather(
                admin_image.prepare_upload(first, "image/png"),
                admin_image.prepare_upload(second, "image/png"),
            )

        assert [ext for _, ext in results] == ["png", "png"]
        assert [step for step, _, _ in events] == ["validate", "shrink", "validate", "shrink"]
        assert events[0][1] == events[1][1]
        assert events[2][1] == events[3][1]
        assert events[0][1] != events[2][1]
        assert ticks() >= 3

    async def test_a_rejected_upload_still_reaches_the_client_as_a_400(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
    ) -> None:
        """A `ValidationError` raised inside the thread is not turned into a 500,
        and the semaphore is released for the next upload."""
        refused = await _upload(client, headers, product_id, data=b"not an image")
        accepted = await _upload(client, headers, product_id)

        assert refused.status_code == 400
        assert refused.json()["error"]["code"] == "INVALID_IMAGE"
        assert accepted.status_code == 201


def largest_that_fits(path: str) -> tuple[int, int]:
    """The most expensive image of `path` the decode budget still accepts.

    Not simply the biggest: at a fixed pixel count the shape decides the cost.
    `shrink_to_fit` scales the longest side down to MAX_STORED_EDGE, so a source
    whose longest side only just exceeds it is barely reduced, and the full
    bitmap and an almost equally large result are alive at once - where a long
    thin image of the same pixel count is reduced to a fraction of itself.
    Minimising the longest side maximises both, so the squarest shape is the
    worst. Measured, 1619x1619 peaks at 120.0 MiB against 105.0 for the 4:3
    image of the same 2.62 megapixels, and the 4:3 shape this used to build let
    the test pass while a permitted image went 20 MiB over the budget.

    Derived from MAX_STORED_EDGE rather than written down, so it stays the worst
    shape if that constant moves. Below the edge nothing is resized and nothing
    is allocated, so when the budget allows fewer pixels than a square of that
    side, the worst case is the flattest image that still exceeds it by one.
    """
    fixed, per_pixel = DECODE_COST[path]
    pixels = (settings.max_image_decode_bytes - fixed) // per_pixel
    side = int(pixels**0.5)
    if side > MAX_STORED_EDGE:
        return (side, side)
    edge = MAX_STORED_EDGE + 1
    return (edge, pixels // edge)


class TestTheLimitIsMemoryRatherThanPixels:
    """`shrink_to_fit` decodes the whole bitmap, and that is what allocates.

    What a pixel costs there is a property of the format - measured, 7 bytes for
    a phone's JPEG against 16 for a WebP - so a single pixel limit would be
    either unsafe for a WebP or useless for a photo. The limit is the memory one
    upload may take, and each format gets the pixel count that fits inside it.
    """

    def test_a_12_megapixel_phone_photo_passes(self) -> None:
        """4080x3072 is the largest 12MP a current phone writes by default."""
        photo = image_bytes("JPEG", (4080, 3072), progressive=True)

        assert validate_image(photo, "image/jpeg") == ("JPEG", "jpg")

    def test_the_same_resolution_costs_a_webp_its_place(self) -> None:
        """The refusal is about the decoder, not the picture: libwebp holds two
        canvases and a copy of the frame where a JPEG holds one bitmap."""
        size = (2400, 1800)
        assert validate_image(image_bytes("JPEG", size), "image/jpeg") == ("JPEG", "jpg")

        with pytest.raises(ValidationError) as refused:
            validate_image(image_bytes("WEBP", size, mode="RGBA"), "image/webp")

        assert refused.value.code == "IMAGE_TOO_MANY_PIXELS"

    @pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
    def test_an_image_stored_untouched_is_never_refused(self, fmt: str) -> None:
        """MAX_STORED_EDGE is 1600, so this one is stored as it arrived (bar the
        metadata, which has no pixels to decode).

        It is accepted because it is never decoded, not because it fits a limit:
        WebP's is 1.9 megapixels, below this image's 2.56, and `validate_image`
        applies the budget only to an image that is decoded - one above
        MAX_STORED_EDGE or to be turned upright. Before that condition
        existed this property had to be bought by keeping every limit above
        1600x1600, which is what made WebP impossible to price - the floor it
        imposed already cost 120.6 MiB on the worst shape.
        """
        assert validate_image(image_bytes(fmt, (1600, 1600)), None)[0] == fmt

    def test_the_refusal_names_a_size_that_would_fit(self) -> None:
        """A 24MP photo - the iPhone default - is refused, and the admin is told
        what to export instead rather than only that something is wrong."""
        with pytest.raises(ValidationError) as refused:
            validate_image(image_bytes("JPEG", (5664, 4248)), "image/jpeg")

        details = refused.value.details
        assert (details["width"], details["height"]) == (5664, 4248)
        # Same shape, so the advice does not silently crop the photo.
        assert details["maxWidth"] / details["maxHeight"] == pytest.approx(5664 / 4248, rel=0.01)
        # And it is advice that works: the size named is accepted.
        suggested = image_bytes("JPEG", (details["maxWidth"], details["maxHeight"]))
        assert validate_image(suggested, "image/jpeg") == ("JPEG", "jpg")


class TestPillowsOwnBombGuard:
    """Pillow refuses enormous images on its own, and used to do it as a 500.

    `Image.open` raises DecompressionBombError above twice MAX_IMAGE_PIXELS
    (89,478,485), before this code reads the size. That exception is a plain
    Exception - not an OSError, not a ValueError - so it passed through the
    handler for unreadable files and reached the client as an internal error,
    for an image whose only fault was being too big.
    """

    async def test_a_header_beyond_pillows_limit_is_a_400(
        self, client: httpx.AsyncClient, headers: dict[str, str], product_id: str
    ) -> None:
        # 16320x12240 is a 200MP phone's full-resolution mode. As a JPEG it
        # would be stopped by the byte limit; a flat PNG of it fits in a few
        # hundred bytes and reaches Pillow.
        bomb = header_only_png(16320, 12240)

        response = await _upload(client, headers, product_id, data=bomb)

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "IMAGE_TOO_MANY_PIXELS"

    def test_our_limit_stays_below_pillows_own(self) -> None:
        """So the two never disagree about an image that is actually accepted.

        Pillow only warns between its limit and twice it; below ours it never
        has an opinion at all.
        """
        fixed, per_pixel = min(DECODE_COST.values(), key=lambda cost: cost[1])
        largest = (settings.max_image_decode_bytes - fixed) // per_pixel

        # None would mean Pillow's own guard is switched off, and then there is
        # nothing to agree with.
        assert Image.MAX_IMAGE_PIXELS is not None
        assert largest <= Image.MAX_IMAGE_PIXELS


#: Measures one decode in a process of its own. Pillow allocates its bitmaps in C
#: and libwebp allocates its canvases outside Pillow, so tracemalloc sees neither
#: and only the operating system's own counter is the truth here.
#:
#: On Linux that counter is `VmHWM`, never `ru_maxrss`. `execve` folds the
#: high-water of the address space it replaces into the new process's
#: `signal->maxrss`, and what it replaces is `fork`'s copy-on-write clone of the
#: parent - so a child of pytest is pinned at pytest's own footprint from its
#: first instruction. Measured: a parent holding 411 MiB, a child that allocates
#: nothing, ru_maxrss 411 MiB against VmHWM 9 MiB. `VmHWM` is the high-water of
#: the mm `execve` itself created and carries nothing from before the exec.
#: Windows has no pre-exec address space to fold in, which is why this was only
#: ever visible on Linux.
#:
#: Windows keeps committed private bytes rather than the symmetrical peak working
#: set: a working set can be trimmed and need not hold every allocated page, and
#: a measurement that under-reports is the one kind this test cannot survive - it
#: would pass a real regression. Committed bytes never under-report. So Linux
#: counts resident pages and Windows counts committed private bytes; decode
#: buffers are written rather than merely reserved, so the two agree closely.
#:
#: The peak is reported from before the decode as well as after, because the
#: subtraction below only means anything if the decode is what moved it.
PEAK_DECODE = """
import os, sys

# (current, peak) private memory of this process, in bytes.
def memory():
    if os.name == "nt":
        import ctypes, ctypes.wintypes as types
        size_t = ctypes.c_size_t
        class Counters(ctypes.Structure):
            # PROCESS_MEMORY_COUNTERS_EX, in the order the API fills it.
            _fields_ = [
                ("cb", types.DWORD), ("faults", types.DWORD),
                ("peak_working_set", size_t), ("working_set", size_t),
                ("quota_peak_paged", size_t), ("quota_paged", size_t),
                ("quota_peak_non_paged", size_t), ("quota_non_paged", size_t),
                ("private", size_t), ("peak_private", size_t), ("private_usage", size_t),
            ]
        kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        kernel32.GetCurrentProcess.restype = types.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [types.HANDLE, ctypes.POINTER(Counters), types.DWORD]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise OSError("GetProcessMemoryInfo failed")
        return counters.private, counters.peak_private
    status = {}
    with open("/proc/self/status") as handle:
        for line in handle:
            key, _, value = line.partition(":")
            if key in ("VmRSS", "VmHWM"):
                status[key] = int(value.split()[0]) * 1024
    return status["VmRSS"], status["VmHWM"]

data = sys.stdin.buffer.read()
from app.services.storage import shrink_to_fit, validate_image

before, peak_before = memory()
image_format, _ = validate_image(data, None)
shrink_to_fit(data, image_format)
_, peak_after = memory()
print(before, peak_before, peak_after)
"""


def peak_decode_bytes(data: bytes) -> int:
    """Peak memory a fresh process takes to validate and shrink `data`."""
    result = subprocess.run(
        [sys.executable, "-c", PEAK_DECODE],
        input=data,
        capture_output=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    assert result.returncode == 0, result.stderr.decode()
    before, peak_before, peak_after = (int(field) for field in result.stdout.split())

    # The decode has to be what set the high-water mark, and this guard is here
    # because the alternative is silent. Reading `ru_maxrss` pinned the peak at
    # pytest's own footprint: all four cases returned the same 208 MiB and
    # nothing in the output looked wrong - four unrelated decoders agreeing to
    # within 0.1% was the only clue, and it took a comparison between the cases
    # to see it at all. A peak the decode never moved is a floor left by
    # something else, so it is refused here rather than reported as a cost.
    assert peak_after > peak_before, (
        f"the peak was already {peak_before / 1024 / 1024:.0f} MiB before decoding "
        f"and the decode did not move it, so this measures something else"
    )

    # Sound because of the guard: the peak was reached during the decode, and at
    # that moment the process held the settled baseline plus the decode itself.
    return peak_after - before


@pytest.mark.skipif(
    sys.platform != "win32" and not sys.platform.startswith("linux"),
    reason="peak memory is read from Windows or /proc",
)
class TestDecodeMemoryIsBounded:
    """The budget is a number in a config file until something measures it.

    Every case here is the largest image its decode path accepts, in the most
    expensive variant of that path, and the assertion is the promise the limit
    makes: one upload never costs more than the budget. Without this, a Pillow
    upgrade that changes a decoder moves the real cost and nothing notices - the
    limit would keep its shape and quietly stop meaning anything.

    Measured while writing it: at the old 50M pixel limit the same images peaked
    at 334 MB (JPEG), 426 MB (PNG) and 830 MB (WebP).
    """

    @pytest.mark.parametrize(
        ("path", "fmt", "mode", "options"),
        [
            # Progressive, because that is what makes libjpeg hold every
            # coefficient of the image at once.
            ("JPEG", "JPEG", "RGB", {"progressive": True}),
            ("JPEG_FULL_CHROMA", "JPEG", "CMYK", {"progressive": True}),
            ("PNG", "PNG", "RGBA", {"compress_level": 1}),
            ("WEBP", "WEBP", "RGBA", {"lossless": True, "method": 0}),
        ],
    )
    def test_the_largest_accepted_image_stays_within_the_budget(
        self, path: str, fmt: str, mode: str, options: dict[str, object]
    ) -> None:
        image = image_bytes(fmt, largest_that_fits(path), mode=mode, **options)
        assert validate_image(image, None)[0] == fmt

        peak = peak_decode_bytes(image)

        assert peak <= settings.max_image_decode_bytes, (
            f"{path} peaked at {peak / 1024 / 1024:.0f} MiB, over the "
            f"{settings.max_image_decode_bytes / 1024 / 1024:.0f} MiB budget"
        )


def largest_that_is_turned(path: str) -> list[tuple[int, int]]:
    """The most expensive images of `path` that are decoded only to be turned.

    No resize is involved, so the longest side is at most MAX_STORED_EDGE and the
    pixel count is what the budget admits. Two shapes, because the cost is not
    only the count: the squarest, and the widest and flattest (the full edge).
    Where the budget is above 1600x1600 the only case is 1600x1600 itself.
    """
    fixed, per_pixel = DECODE_COST[path]
    pixel_count = (settings.max_image_decode_bytes - fixed) // per_pixel
    side = min(MAX_STORED_EDGE, math.isqrt(pixel_count))
    shapes = [(side, side)]
    if side < MAX_STORED_EDGE:
        shapes.append((MAX_STORED_EDGE, pixel_count // MAX_STORED_EDGE))
    return shapes


@pytest.mark.skipif(
    sys.platform != "win32" and not sys.platform.startswith("linux"),
    reason="peak memory is read from Windows or /proc",
)
class TestDecodeMemoryIsBoundedWhenOnlyTurning:
    """An image that fits is no longer left undecoded when it has to be turned.

    `TestDecodeMemoryIsBounded` covers what is resized. This is the other way to
    be decoded: at most 1600x1600 with an EXIF Orientation, where the bitmap and
    its rotated copy are alive together. The largest image `validate_image`
    admits on each path must still stay inside the budget.
    """

    @pytest.mark.parametrize(
        ("path", "fmt", "mode", "options"),
        [
            ("JPEG", "JPEG", "RGB", {"progressive": True}),
            ("JPEG_FULL_CHROMA", "JPEG", "CMYK", {"progressive": True}),
            ("PNG", "PNG", "RGBA", {"compress_level": 1}),
            ("WEBP", "WEBP", "RGBA", {"lossless": True, "method": 0}),
        ],
    )
    def test_the_largest_accepted_image_that_is_turned_stays_within_the_budget(
        self, path: str, fmt: str, mode: str, options: dict[str, object]
    ) -> None:
        for size in largest_that_is_turned(path):
            image = image_bytes(fmt, size, mode=mode, exif=exif_bytes(6), **options)
            assert validate_image(image, None)[0] == fmt

            peak = peak_decode_bytes(image)

            print(f"turned {path} {size}: {peak / 1024 / 1024:.1f} MiB")
            assert peak <= settings.max_image_decode_bytes, (
                f"{path} {size} peaked at {peak / 1024 / 1024:.0f} MiB, over the "
                f"{settings.max_image_decode_bytes / 1024 / 1024:.0f} MiB budget"
            )


SERVICE_KEY = "service-role-key-that-must-not-leak"


class FakeSupabase:
    """Answers Supabase Storage's HTTP calls with a chosen response.

    The fake sits under httpx, not in place of SupabaseStorage: the class under
    test builds the real request and reads the real response. Mocking the class
    itself is how 1ebe26b stayed green while broken.
    """

    def __init__(self) -> None:
        self.status = 200
        self.body: object = {"message": "Successfully deleted"}
        self.requests: list[httpx.Request] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)


@pytest.fixture
def supabase(monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[SupabaseStorage, FakeSupabase]]:
    fake = FakeSupabase()
    transport = httpx.MockTransport(fake.handle)

    def client(**kwargs: object) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, **kwargs)  # type: ignore[arg-type]

    # Only storage.py's view of httpx changes; the test client keeps the real one.
    monkeypatch.setattr(storage_module, "httpx", types.SimpleNamespace(AsyncClient=client))
    backend = SupabaseStorage("project", SERVICE_KEY, "products")
    app.dependency_overrides[get_storage] = lambda: backend
    yield backend, fake
    app.dependency_overrides.pop(get_storage, None)


class TestSupabaseDelete:
    """A delete Supabase refused must not be reported as done.

    The file would stay public at its URL while the panel said it was gone.
    """

    async def test_a_missing_object_counts_as_deleted(
        self, supabase: tuple[SupabaseStorage, FakeSupabase]
    ) -> None:
        backend, fake = supabase
        fake.status, fake.body = 404, {"message": "Object not found"}

        await backend.delete("products/p/gone.png")

        (request,) = fake.requests
        assert request.method == "DELETE"
        assert request.url.path == "/storage/v1/object/products/products/p/gone.png"

    async def test_a_400_whose_body_says_404_counts_as_deleted(
        self, supabase: tuple[SupabaseStorage, FakeSupabase]
    ) -> None:
        backend, fake = supabase
        fake.status, fake.body = 400, {"statusCode": "404", "error": "not_found"}

        await backend.delete("products/p/gone.png")

    @pytest.mark.parametrize("status", [401, 403, 500, 503])
    async def test_any_other_failure_is_raised(
        self, supabase: tuple[SupabaseStorage, FakeSupabase], status: int
    ) -> None:
        backend, fake = supabase
        fake.status, fake.body = status, {"error": "nope"}

        with pytest.raises(AppError) as raised:
            await backend.delete("products/p/kept.png")

        assert raised.value.code == "STORAGE_DELETE_FAILED"
        assert raised.value.status_code == 502
        assert raised.value.details == {"status": status}

    async def test_a_plain_400_is_not_mistaken_for_a_missing_object(
        self, supabase: tuple[SupabaseStorage, FakeSupabase]
    ) -> None:
        backend, fake = supabase
        fake.status, fake.body = 400, {"statusCode": "400", "error": "InvalidKey"}

        with pytest.raises(AppError):
            await backend.delete("products/p/kept.png")


async def _stored_image(db: AsyncSession, product_id: str) -> ProductImage:
    image = ProductImage(
        product_id=uuid.UUID(product_id),
        url=f"https://project.supabase.co/storage/v1/object/public/products/products/{product_id}/a.png",
        position=0,
        is_primary=True,
    )
    db.add(image)
    await db.flush()
    return image


@pytest.mark.parametrize("status", [403, 500])
async def test_a_refused_storage_delete_reaches_the_admin_and_keeps_the_row(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    db: AsyncSession,
    supabase: tuple[SupabaseStorage, FakeSupabase],
    caplog: pytest.LogCaptureFixture,
    status: int,
) -> None:
    """The row stays so the admin can retry; nothing echoes the key."""
    _, fake = supabase
    fake.status = status
    image_id = (await _stored_image(db, product_id)).id

    with caplog.at_level("DEBUG"):
        response = await client.delete(
            f"{ADMIN}/products/{product_id}/images/{image_id}", headers=headers
        )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "STORAGE_DELETE_FAILED"
    assert response.json()["error"]["details"] == {"status": status}
    assert len(fake.requests) == 1
    db.expire_all()
    assert await db.scalar(select(ProductImage).where(ProductImage.id == image_id)) is not None
    for leaked in (SERVICE_KEY, "Bearer", "apikey"):
        assert leaked not in response.text
        assert leaked not in caplog.text


async def test_an_already_missing_object_still_deletes_the_row(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    db: AsyncSession,
    supabase: tuple[SupabaseStorage, FakeSupabase],
) -> None:
    _, fake = supabase
    fake.status, fake.body = 404, {"message": "Object not found"}
    image = await _stored_image(db, product_id)
    image_id = image.id

    response = await client.delete(
        f"{ADMIN}/products/{product_id}/images/{image_id}", headers=headers
    )

    assert response.status_code == 204
    assert len(fake.requests) == 1
    db.expire_all()
    assert await db.scalar(select(ProductImage).where(ProductImage.id == image_id)) is None
