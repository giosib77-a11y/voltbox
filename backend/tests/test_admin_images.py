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
from typing import ClassVar

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


def png_with_late_exif(png: bytes, exif: bytes) -> bytes:
    """`png` with an `eXIf` chunk between its last IDAT and IEND.

    A PNG carries EXIF without the `Exif\\0\\0` prefix that `exif_bytes` writes.
    """
    payload = exif.removeprefix(b"Exif\x00\x00")
    return png[:-12] + png_chunk(b"eXIf", payload) + png[-12:]


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


@pytest.mark.parametrize("cut", [1, 3, 5, 8, 11])
async def test_a_png_cut_inside_its_last_chunk_is_a_400_not_a_500(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    storage: InMemoryStorage,
    cut: int,
) -> None:
    """A partly downloaded file ends wherever the connection dropped.

    Cutting 5 or 8 bytes leaves IEND's length and an incomplete chunk header, and
    Pillow answers that one with a `SyntaxError` ("broken PNG file") where every
    other cut raises an `OSError` - the handler once let it through as a 500.
    """
    data = image_bytes("PNG", size=(64, 64))[:-cut]

    response = await _upload(client, headers, product_id, data=data)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IMAGE"
    assert storage.objects == {}


# --- A picture damaged where only the decode finds it is a 400 (A-097) -------
#
# `validate_image` parses structure (`verify()`) and for a JPEG checks nothing after
# the scan header, so files whose pixel data is broken pass it. The decode in
# `shrink_to_fit` is what meets the damage, and Pillow reports it as an OSError
# ("image file is truncated", "broken data stream", "failed to read next frame")
# - and, for a PNG chunk after the pixel data, as a ValueError, a SyntaxError or
# an IndexError. All of them used to reach the client as a 500.

#: What a big JPEG's last two bytes (the EOI) become when the upload was cut or
#: mangled. The audit's three tails.
DAMAGED_JPEG_TAILS = {"eoi-cut": b"", "eoi-is-ff": b"\xff", "eoi-is-ff-d8": b"\xff\xd8"}

#: The two reasons a file is decoded at all: it is too large, or it must be turned.
#: `(size, encoder options)`; 400x300 is far below the edge, so only the EXIF
#: Orientation makes the second one a decode.
DECODED_BECAUSE: dict[str, tuple[tuple[int, int], dict[str, object]]] = {
    "too-large": ((1700, 1300), {}),
    "rotated": ((400, 300), {"exif": exif_bytes(6)}),
}


async def _assert_refused_as_unreadable(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    storage: InMemoryStorage,
    data: bytes,
    *,
    filename: str,
    content_type: str,
) -> None:
    # The premise: the file gets past validation, so the 400 below comes from the
    # decode and not from the checks that always worked.
    validate_image(data, None)

    response = await _upload(
        client, headers, product_id, data=data, filename=filename, content_type=content_type
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IMAGE"
    assert storage.objects == {}


@pytest.mark.parametrize("tail", DAMAGED_JPEG_TAILS.values(), ids=DAMAGED_JPEG_TAILS.keys())
@pytest.mark.parametrize("case", DECODED_BECAUSE)
async def test_a_jpeg_with_damaged_entropy_data_is_a_400_not_a_500(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    storage: InMemoryStorage,
    case: str,
    tail: bytes,
) -> None:
    size, options = DECODED_BECAUSE[case]
    data = encode(patterned(size), "JPEG", **options)[:-2] + tail

    await _assert_refused_as_unreadable(
        client,
        headers,
        product_id,
        storage,
        data,
        filename="p.jpg",
        content_type="image/jpeg",
    )


def png_with_pixel_stream(png: bytes, mutate: Callable[[bytes], bytes]) -> bytes:
    """`png` with its IDAT chunks replaced by one holding `mutate(zlib stream)`.

    Every chunk keeps a valid CRC, which is what makes the damage invisible to
    `verify()`: the container is sound and only the compressed pixels are not.
    """
    chunks = png_chunks(png)
    stream = b"".join(chunk[8:-4] for chunk in chunks if chunk[4:8] == b"IDAT")
    out = [b"\x89PNG\r\n\x1a\n"]
    placed = False
    for chunk in chunks:
        if chunk[4:8] != b"IDAT":
            out.append(chunk)
        elif not placed:
            out.append(png_chunk(b"IDAT", mutate(stream)))
            placed = True
    return b"".join(out)


def png_with_chunk_after_pixels(png: bytes, kind: bytes, payload: bytes) -> bytes:
    """`png` with a chunk between its last IDAT and IEND, CRC correct."""
    return png[:-12] + png_chunk(kind, payload) + png[-12:]


def _bad_filter_byte(stream: bytes) -> bytes:
    raw = bytearray(zlib.decompress(stream))
    raw[0] = 9  # the first scanline's filter type; 0-4 are defined
    return zlib.compress(bytes(raw))


#: Damage to a PNG that `verify()` cannot see, by the exception Pillow answers with.
DAMAGED_PNGS: dict[str, Callable[[bytes], bytes]] = {
    # OSError: the zlib stream ends before the pixels do.
    "zlib-stream-cut": lambda png: png_with_pixel_stream(png, lambda s: s[: len(s) // 2]),
    "zlib-stream-empty": lambda png: png_with_pixel_stream(png, lambda s: b""),
    # OSError: not a zlib stream at all.
    "zlib-header-broken": lambda png: png_with_pixel_stream(png, lambda s: b"\x00\x00" + s[2:]),
    # OSError: a filter type the format does not define.
    "filter-type-undefined": lambda png: png_with_pixel_stream(png, _bad_filter_byte),
    # ValueError: a chunk after the pixels that is too short for its own type.
    "pHYs-too-short": lambda png: png_with_chunk_after_pixels(png, b"pHYs", b"\x00"),
    "tRNS-too-short-for-rgb": lambda png: png_with_chunk_after_pixels(png, b"tRNS", b"\x00"),
    # SyntaxError: an animation chunk with no animation.
    "stray-fdAT": lambda png: png_with_chunk_after_pixels(png, b"fdAT", b"\x00\x00\x00\x00abc"),
    # IndexError: an ICC profile chunk with no name, so no compression method.
    "iCCP-empty": lambda png: png_with_chunk_after_pixels(png, b"iCCP", b""),
}


@pytest.mark.parametrize("damage", DAMAGED_PNGS)
@pytest.mark.parametrize("case", DECODED_BECAUSE)
async def test_a_png_with_damaged_pixel_data_is_a_400_not_a_500(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    storage: InMemoryStorage,
    case: str,
    damage: str,
) -> None:
    size, options = DECODED_BECAUSE[case]
    data = DAMAGED_PNGS[damage](encode(patterned(size), "PNG", **options))

    await _assert_refused_as_unreadable(
        client,
        headers,
        product_id,
        storage,
        data,
        filename="p.png",
        content_type="image/png",
    )


def webp_with_damaged_pixels(webp: bytes) -> bytes:
    """`webp` with 200 bytes in the middle of its lossless image data flipped.

    The RIFF structure is rebuilt around it, so every size still adds up and
    `verify()` has nothing to object to.
    """
    chunks: list[tuple[bytes, bytes]] = []
    for fourcc, payload in riff_chunks(webp, 12, len(webp)):
        if fourcc == b"VP8L":
            middle = len(payload) // 2
            flipped = bytes(b ^ 0x5A for b in payload[middle : middle + 200])
            payload = payload[:middle] + flipped + payload[middle + 200 :]
        chunks.append((fourcc, payload))
    return webp_from_chunks(chunks)


@pytest.mark.parametrize(
    "case, size, options",
    [
        # 1601x1187 is the largest WebP the decode budget admits.
        ("too-large", (1601, 1187), {}),
        ("rotated", (300, 200), {"exif": exif_bytes(6)}),
    ],
)
async def test_a_webp_with_damaged_image_data_is_a_400_not_a_500(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    storage: InMemoryStorage,
    case: str,
    size: tuple[int, int],
    options: dict[str, object],
) -> None:
    data = webp_with_damaged_pixels(encode(patterned(size), "WEBP", lossless=True, **options))

    await _assert_refused_as_unreadable(
        client,
        headers,
        product_id,
        storage,
        data,
        filename="p.webp",
        content_type="image/webp",
    )


# --- A header that contradicts itself is a 400 as well ------------------------
#
# Two files that Pillow opens and then trips over with an IndexError of its own,
# inside `validate_image` and after `_open` (which only converts it there).


def jpeg_with_component_specs(jpeg: bytes, declared: int, listed: int) -> bytes:
    """`jpeg` whose SOF0 declares `declared` components and describes `listed`.

    Pillow fills its per-component table from the length of the segment, not from
    the declared count, and `_open` does not compare the two.
    """
    pos = 2
    while jpeg[pos + 1] != 0xC0:
        pos += 2 + int.from_bytes(jpeg[pos + 2 : pos + 4], "big")
    end = pos + 2 + int.from_bytes(jpeg[pos + 2 : pos + 4], "big")
    precision_and_size = jpeg[pos + 4 : pos + 9]
    specs = b"".join(bytes((i + 1, 0x22 if i == 0 else 0x11, 0)) for i in range(listed))
    body = precision_and_size + bytes((declared,)) + specs
    return jpeg[:pos] + b"\xff\xc0" + (len(body) + 2).to_bytes(2, "big") + body + jpeg[end:]


def png_without_pixel_data() -> bytes:
    """A signature, a valid IHDR and IEND with nothing between: every CRC is right."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0))
        + png_chunk(b"IEND", b"")
    )


@pytest.mark.parametrize("listed", [0, 1, 2])
async def test_a_jpeg_that_declares_more_components_than_it_describes_is_a_400(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    product_id: str,
    storage: InMemoryStorage,
    listed: int,
) -> None:
    """Pillow reads the sampling factors of component 0, 1 and 2 to price the decode."""
    data = jpeg_with_component_specs(encode(patterned((400, 300)), "JPEG"), 3, listed)
    # The premise: Pillow accepts the header, so the refusal is not its own.
    with Image.open(io.BytesIO(data)) as probe:
        assert probe.mode == "RGB"
        assert len(probe.layer) == listed  # type: ignore[attr-defined]

    response = await _upload(
        client, headers, product_id, data=data, filename="p.jpg", content_type="image/jpeg"
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IMAGE"
    assert storage.objects == {}


async def test_a_png_with_no_pixel_data_is_a_400(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str, storage: InMemoryStorage
) -> None:
    """`verify()` seeks to the first IDAT, and there is no tile to ask."""
    response = await _upload(client, headers, product_id, data=png_without_pixel_data())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IMAGE"
    assert storage.objects == {}


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

    def test_a_webp_is_not_saved_with_the_slowest_method(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """libwebp's `method=6` took 2.2-4.0 s on a 1600px WebP with partly
        transparent pixels, against 0.2-0.7 s for methods 4 and 5, for a file 2-4%
        smaller; the encoder runs under Semaphore(1), so every other upload waited
        that long. The measurement is in `shrink_to_fit`."""
        big = image_bytes("WEBP", (1700, 1700), mode="RGBA", lossless=True, method=0)
        saves: list[dict[str, object]] = []
        real_save = Image.Image.save

        def spy(self: Image.Image, fp: object, format: str | None = None, **params: object) -> None:
            saves.append({"format": format, **params})
            real_save(self, fp, format=format, **params)  # type: ignore[arg-type]

        monkeypatch.setattr(Image.Image, "save", spy)

        shrink_to_fit(big, "WEBP")

        assert [save["format"] for save in saves] == ["WEBP"]
        assert saves[0]["method"] == 5


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

    @pytest.mark.parametrize("orientation", range(2, 9))
    def test_a_png_whose_exif_follows_the_pixels_is_turned_like_one_whose_exif_precedes_them(
        self, orientation: int
    ) -> None:
        """The PNG spec allows `eXIf` on either side of IDAT. Pillow has it at open
        only when it comes first, so a late one used to read as upright, was
        deleted by the stripper, and the photo came out sideways."""
        picture = patterned((60, 40))
        early = encode(picture, "PNG", exif=exif_bytes(orientation))
        late = png_with_late_exif(encode(picture, "PNG"), exif_bytes(orientation))
        assert png_chunk_types(early).index(b"eXIf") < png_chunk_types(early).index(b"IDAT")
        assert png_chunk_types(late).index(b"eXIf") > png_chunk_types(late).index(b"IDAT")

        assert validate_image(late, "image/png") == ("PNG", "png")
        stored = shrink_to_fit(late, "PNG")

        assert pixels(stored) == pixels(shrink_to_fit(early, "PNG"))
        assert pixels(stored)[1] == ((40, 60) if orientation >= 5 else (60, 40))
        assert png_chunk_types(stored).count(b"eXIf") == 0

    async def test_a_late_exif_png_is_stored_upright_through_the_upload(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
    ) -> None:
        picture = Image.new("RGB", (1200, 900), (255, 0, 0))
        picture.paste((0, 0, 255), (600, 0, 1200, 900))
        photo = png_with_late_exif(encode(picture, "PNG"), exif_bytes(6, gps=True, make="Acme"))

        stored = await self._store(client, headers, storage, product_id, photo, "png")

        assert png_chunk_types(stored).count(b"eXIf") == 0
        assert b"Acme" not in stored
        mode, size, _ = pixels(stored)
        assert (mode, size) == ("RGB", (900, 1200))
        with Image.open(io.BytesIO(stored)) as saved:
            rgb = saved.convert("RGB")
            top = rgb.getpixel((450, 100))
            bottom = rgb.getpixel((450, 1100))
        assert isinstance(top, tuple)
        assert isinstance(bottom, tuple)
        assert top[0] > 200 > top[2]
        assert bottom[2] > 200 > bottom[0]

    @pytest.mark.parametrize("late", [False, True])
    def test_a_png_that_must_be_turned_is_costed_wherever_its_exif_sits(
        self, monkeypatch: pytest.MonkeyPatch, late: bool
    ) -> None:
        """The budget is applied to an image that is decoded, and a late `eXIf` makes
        the decode as real as an early one: an over-budget file is refused alike."""
        fixed, per_pixel = DECODE_COST["PNG"]
        monkeypatch.setattr(settings, "max_image_decode_bytes", fixed + 1_000_000 * per_pixel)
        upright = encode(patterned((1600, 1600)), "PNG")
        assert validate_image(upright, None)[0] == "PNG"  # never decoded: not costed
        exif = exif_bytes(6)
        turned = (
            png_with_late_exif(upright, exif)
            if late
            else encode(patterned((1600, 1600)), "PNG", exif=exif)
        )

        with pytest.raises(ValidationError) as refused:
            validate_image(turned, None)

        assert refused.value.code == "IMAGE_TOO_MANY_PIXELS"

    @pytest.mark.parametrize("payload", [b"", b"not exif at all", b"Exif\x00\x00II*\x00\xff\xff"])
    def test_an_unreadable_late_exif_is_not_a_rotation_and_not_a_500(self, payload: bytes) -> None:
        original = png_with_late_exif(encode(patterned((60, 40)), "PNG"), payload)

        assert validate_image(original, "image/png") == ("PNG", "png")
        stored = shrink_to_fit(original, "PNG")

        assert pixels(stored) == pixels(original)
        assert png_chunk_types(stored).count(b"eXIf") == 0

    def test_a_png_cut_short_after_its_late_exif_is_invalid_not_a_500(self) -> None:
        good = png_with_late_exif(encode(patterned((60, 40)), "PNG"), exif_bytes(6))

        inside_exif = good.index(b"eXIf") + 8 + 2  # in the payload, past the header
        for broken in (good[:-12], good[:-20], good[:inside_exif]):
            with pytest.raises(ValidationError) as refused:
                validate_image(broken, "image/png")
            assert refused.value.code == "INVALID_IMAGE"

    def test_the_chunk_walk_that_finds_a_late_exif_is_cheap_on_a_file_of_tiny_chunks(self) -> None:
        """5 MiB of empty chunks is the worst case for a walk that does one step per
        chunk: Pillow's `verify()` takes as many steps (and checks each CRC)."""
        clean = encode(patterned((16, 16)), "PNG")
        filler = png_chunk(b"prVT", b"")
        count = (settings.max_image_bytes - len(clean)) // len(filler)
        hostile = clean[:-12] + filler * count + clean[-12:]
        assert len(hostile) <= settings.max_image_bytes

        started = time.perf_counter()
        assert storage_module._png_exif(hostile) is None
        elapsed = time.perf_counter() - started

        assert elapsed < 2.0, f"{elapsed:.2f}s for {count} chunks"

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

    def test_a_jpeg_of_standalone_markers_is_refused_by_count_not_walked_to_the_end(self) -> None:
        """JPEG `verify()` checks nothing after SOS, so 5 MiB of `FF 01` is a valid
        upload to everything but the walk: 2.5 M iterations (measured 1.0 s) without
        a cap on the markers."""
        limit = storage_module._MAX_JPEG_MARKERS
        clean = encode(patterned((64, 48)), "JPEG")
        walk = storage_module._STRIP_METADATA["JPEG"]

        too_many = clean[:2] + b"\xff\x01" * limit + clean[2:]
        outside_scan = b"\xff\xd8" + b"\xff\x01" * (settings.max_image_bytes // 2)
        stuffed_in_scan = clean[:-2] + b"\xff\xff\x00" * limit + clean[-2:]
        for hostile in (too_many, outside_scan, stuffed_in_scan):
            with pytest.raises(ValidationError) as refused:
                walk(hostile)
            assert refused.value.code == "INVALID_IMAGE"

        # A file just under the cap is a file like any other; the markers are kept.
        room = limit - len(jpeg_markers(clean)) - 1
        assert walk(clean[:2] + b"\xff\x01" * room + clean[2:]) == (
            clean[:2] + b"\xff\x01" * room + clean[2:]
        )

    def test_the_marker_cap_counts_every_marker_and_not_one_too_many(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The EOI is a marker too: a file with exactly `n` of them passes at `n`
        and is refused at `n - 1`, so a legitimate file has nothing to fear from
        an off-by-one."""
        clean = encode(patterned((64, 48)), "JPEG")
        count = len(jpeg_markers(clean)) + 1  # header segments up to SOS, then EOI
        walk = storage_module._STRIP_METADATA["JPEG"]

        monkeypatch.setattr(storage_module, "_MAX_JPEG_MARKERS", count)
        assert walk(clean) == clean

        monkeypatch.setattr(storage_module, "_MAX_JPEG_MARKERS", count - 1)
        with pytest.raises(ValidationError) as refused:
            walk(clean)
        assert refused.value.code == "INVALID_IMAGE"

    def test_restart_markers_in_a_scan_do_not_count_against_the_cap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A photo with a restart marker per block has thousands of RSTn; they are
        entropy data to the walk, not segments."""
        restarts = encode(patterned((400, 300)), "JPEG", restart_marker_blocks=1)
        # RSTn cycles through D0..D7, so all eight codes are counted.
        assert sum(restarts.count(bytes((0xFF, code))) for code in range(0xD0, 0xD8)) > 100
        monkeypatch.setattr(storage_module, "_MAX_JPEG_MARKERS", len(jpeg_markers(restarts)) + 1)

        assert storage_module._STRIP_METADATA["JPEG"](restarts) == restarts

    def test_a_long_run_of_fill_bytes_before_a_marker_is_skipped(self) -> None:
        clean = encode(patterned((64, 48)), "JPEG")
        padded = clean[:2] + b"\xff" * 100_000 + clean[2:]

        assert storage_module._STRIP_METADATA["JPEG"](padded) == clean

    def test_a_small_jpeg_with_no_eoi_is_refused_not_decoded(self) -> None:
        """At or below the edge a decode would be unbudgeted, so there is no
        fallback to one."""
        original = encode(patterned((400, 300)), "JPEG")[:-2]

        with pytest.raises(ValidationError) as refused:
            shrink_to_fit(original, "JPEG")

        assert refused.value.code == "INVALID_IMAGE"

    # Where the EOI should be: Pillow decodes the whole picture (it stops after the
    # last MCU and never looks at what follows), but the walk cannot reach an EOI.
    # (A file that merely loses its EOI is no example: Pillow refuses to decode it,
    # "image file is truncated", so it never gets as far as the walk.)
    UNWALKABLE_TAILS: ClassVar[dict[str, bytes]] = {
        "marker length past the end": b"\xff\xe1\xff\xff",
        "more standalone markers than the cap": b"\xff\x01"
        * (storage_module._MAX_JPEG_MARKERS + 1),
        "no marker at all": b"\x00\x00\x00\x00",
    }

    @pytest.mark.parametrize("tail", UNWALKABLE_TAILS)
    def test_a_resized_jpeg_the_walk_cannot_read_is_stored_as_the_re_encode(
        self, tail: str
    ) -> None:
        """A decode had already been paid for and a clean re-encode of it exists,
        so the comparison with the stripped original is skipped rather than
        turning the upload into a 400."""
        exif = exif_bytes(gps=True, make="SecretMaker")
        original = encode(patterned((1700, 1300)), "JPEG", exif=exif)[:-2]
        original += self.UNWALKABLE_TAILS[tail]
        with pytest.raises(ValidationError):  # the premise: the walk refuses it
            storage_module._STRIP_METADATA["JPEG"](original)
        assert validate_image(original, None)[0] == "JPEG"

        stored = shrink_to_fit(original, "JPEG")

        with Image.open(io.BytesIO(stored)) as saved:
            assert saved.format == "JPEG"
            assert max(saved.size) == MAX_STORED_EDGE
            assert not saved.getexif()
        assert b"Exif" not in stored
        assert b"SecretMaker" not in stored

    @pytest.mark.parametrize("tail", UNWALKABLE_TAILS)
    async def test_an_upload_of_such_a_jpeg_is_stored_not_refused(
        self,
        tail: str,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
    ) -> None:
        original = encode(patterned((1700, 1300)), "JPEG", exif=exif_bytes(gps=True))[:-2]
        original += self.UNWALKABLE_TAILS[tail]

        response = await _upload(
            client, headers, product_id, data=original, filename="p.jpg", content_type="image/jpeg"
        )

        assert response.status_code == 201
        stored = only_object(storage)
        with Image.open(io.BytesIO(stored)) as saved:
            assert max(saved.size) == MAX_STORED_EDGE
            assert not saved.getexif()

    @pytest.mark.parametrize("tail", UNWALKABLE_TAILS)
    def test_the_same_file_at_the_edge_is_still_refused(self, tail: str) -> None:
        """What still holds: at or below the edge and upright nothing is decoded,
        so there is no re-encode to fall back on."""
        original = encode(patterned((400, 300)), "JPEG")[:-2] + self.UNWALKABLE_TAILS[tail]
        assert validate_image(original, None)[0] == "JPEG"

        with pytest.raises(ValidationError) as refused:
            shrink_to_fit(original, "JPEG")

        assert refused.value.code == "INVALID_IMAGE"


# --- Only chunks known to be harmless are stored (A-058) ---------------------
#
# The stripper used to be a denylist for PNG (EXIF, text, tIME) and WebP (EXIF,
# XMP), so anything it had not been told about - C2PA, which may name the author,
# an Apple thumbnail index, a tool's private chunk - was published in the public
# bucket, while the JPEG walker dropped C2PA (APP11) and kept APP0 and APP14 whole.


def png_chunks(data: bytes) -> list[bytes]:
    """Every chunk of a PNG whole - length, type, data and CRC."""
    chunks: list[bytes] = []
    pos = 8
    while pos < len(data):
        end = pos + 12 + int.from_bytes(data[pos : pos + 4], "big")
        chunks.append(data[pos:end])
        pos = end
    return chunks


def png_after_header(png: bytes, *chunks: bytes) -> bytes:
    """`png` with `chunks` right after IHDR, where Apple writes `iDOT` too."""
    header_end = 8 + 12 + 13
    return png[:header_end] + b"".join(chunks) + png[header_end:]


#: Chunks that identify, or may identify, whoever made the picture. Each payload
#: carries a marker that must not be found in the stored file.
PNG_IDENTITY = {
    b"caBX": b"c2pa-secret",
    b"exIf": b"exif-secret",
    b"zxIf": b"zxif-secret",
    b"iDOT": b"idot-secret",
    b"prVt": b"private-secret",
    b"sPLT": b"splt-secret",
}


def png_with_identity(original: bytes) -> bytes:
    return png_after_header(original, *(png_chunk(k, v) for k, v in PNG_IDENTITY.items()))


def riff_chunks(data: bytes, pos: int, end: int) -> list[tuple[bytes, bytes]]:
    """The `(FourCC, payload)` chunks of `data[pos:end]`, padding not included."""
    chunks: list[tuple[bytes, bytes]] = []
    while pos < end:
        length = int.from_bytes(data[pos + 4 : pos + 8], "little")
        chunks.append((data[pos : pos + 4], data[pos + 8 : pos + 8 + length]))
        pos += 8 + length + length % 2
    return chunks


def riff_chunk(fourcc: bytes, payload: bytes) -> bytes:
    return fourcc + len(payload).to_bytes(4, "little") + payload + b"\x00" * (len(payload) % 2)


def webp_from_chunks(chunks: list[tuple[bytes, bytes]]) -> bytes:
    body = b"WEBP" + b"".join(riff_chunk(fourcc, payload) for fourcc, payload in chunks)
    return b"RIFF" + len(body).to_bytes(4, "little") + body


WEBP_IDENTITY = {b"C2PA": b"c2pa-secret", b"prVt": b"private-secret!", b"IPTC": b"iptc-secret"}


def webp_with_identity(original: bytes) -> bytes:
    """Unknown chunks right after the picture and as the last chunk. After the
    picture because that is where the format allows them: libwebp refuses a file
    with one between the header and the image data."""
    chunks = riff_chunks(original, 12, len(original))
    image = next(i for i, (fourcc, _) in enumerate(chunks) if fourcc in (b"VP8 ", b"VP8L"))
    unknown = list(WEBP_IDENTITY.items())
    chunks[image + 1 : image + 1] = unknown[:2]
    chunks.append(unknown[2])
    return webp_from_chunks(chunks)


def jpeg_with_identity(original: bytes) -> bytes:
    return jpeg_with_segments(
        original,
        (0xE0, b"JFXX\x00\x10" + b"thumb-secret"),  # APP0, an extension with a thumbnail
        (0xEB, b"c2pa-secret"),  # APP11, C2PA
        (0xEE, b"Phone\x00" + b"app14-secret"),  # APP14 that is not Adobe's
    )


def jpeg_segment(data: bytes, marker: int) -> bytes:
    """The first header segment with this marker, whole: marker, length, payload."""
    pos = 2
    while data[pos + 1] != marker:
        assert data[pos + 1] != 0xDA, f"no segment {marker:#x} before the scan"
        pos += 2 + int.from_bytes(data[pos + 2 : pos + 4], "big")
    return data[pos : pos + 2 + int.from_bytes(data[pos + 2 : pos + 4], "big")]


def jpeg_with_payload(data: bytes, marker: int, payload: bytes) -> bytes:
    """`data` with the first segment of this marker given another payload."""
    old = jpeg_segment(data, marker)
    new = bytes((0xFF, marker)) + (len(payload) + 2).to_bytes(2, "big") + payload
    return data.replace(old, new, 1)


#: The first 12 bytes of a JFIF payload: `JFIF\0`, version 1.01, units, density 72
#: dpi. The thumbnail's width and height (two bytes) follow, then the thumbnail.
JFIF_HEADER = b"JFIF\x00\x01\x01\x01\x00\x48\x00\x48"


def animation_frames(data: bytes) -> list[bytes]:
    with Image.open(io.BytesIO(data)) as animated:
        frames: list[bytes] = []
        for index in range(animated.n_frames):  # type: ignore[attr-defined]
            animated.seek(index)
            frames.append(animated.convert("RGBA").tobytes())
        return frames


def three_frames() -> list[Image.Image]:
    base = patterned((64, 48))
    return [
        base,
        base.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
        base.transpose(Image.Transpose.ROTATE_180),
    ]


#: Small, and above MAX_STORED_EDGE: a small animation used to keep every frame
#: and a large one used to become its first frame on the re-encode (A-101).
ANIMATION_SIZES = {"small": (64, 48), "large": (1700, 40)}


def animated_png(size: tuple[int, int], frames: int) -> bytes:
    base = patterned(size)
    images = [
        base,
        base.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
        base.transpose(Image.Transpose.ROTATE_180),
    ][:frames]
    return encode(images[0], "PNG", save_all=True, append_images=images[1:])


def animated_webp(size: tuple[int, int], frames: int) -> bytes:
    base = patterned(size)
    images = [
        base,
        base.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
        base.transpose(Image.Transpose.ROTATE_180),
    ][:frames]
    return encode(images[0], "WEBP", save_all=True, append_images=images[1:], lossless=True)


def one_frame_apng(size: tuple[int, int]) -> bytes:
    """An APNG whose `acTL` says one frame: the first frame of a written animation,
    nothing after it. Pillow reports `n_frames == 1` for it."""
    kept: list[bytes] = []
    frame_controls = 0
    for chunk in png_chunks(animated_png(size, 2)):
        kind = chunk[4:8]
        if kind == b"acTL":
            chunk = png_chunk(b"acTL", struct.pack(">II", 1, 0))
        elif kind == b"fcTL":
            frame_controls += 1
        if frame_controls > 1 and kind != b"IEND":
            continue
        kept.append(chunk)
    return b"\x89PNG\r\n\x1a\n" + b"".join(kept)


def one_frame_animated_webp(size: tuple[int, int]) -> bytes:
    """A `VP8X`-animated WebP (`ANIM` and one `ANMF`): what a tool exports for a
    "single frame animation"."""
    written = animated_webp(size, 2)
    parts = riff_chunks(written, 12, len(written))
    frame = next(p for f, p in parts if f == b"ANMF")
    return webp_from_chunks([*[(f, p) for f, p in parts if f != b"ANMF"], (b"ANMF", frame)])


class TestAnimatedImagesAreRefused:
    """A product photo does not need to move, and the two animated paths disagreed
    about what is stored (A-101): one that fits kept every frame, one that was
    reduced became its first frame. Both are refused instead - from what Pillow
    reads at open, so nothing is decoded to find out."""

    @pytest.mark.parametrize("size", ANIMATION_SIZES.values(), ids=ANIMATION_SIZES)
    @pytest.mark.parametrize("frames", [2, 3])
    @pytest.mark.parametrize("fmt", ["png", "webp"])
    async def test_an_animation_is_a_400_and_stores_nothing(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        product_id: str,
        storage: InMemoryStorage,
        fmt: str,
        frames: int,
        size: tuple[int, int],
    ) -> None:
        build = animated_png if fmt == "png" else animated_webp
        data = build(size, frames)
        with Image.open(io.BytesIO(data)) as probe:
            assert probe.n_frames == frames  # type: ignore[attr-defined]

        response = await _upload(
            client, headers, product_id, data=data, filename=f"p.{fmt}", content_type=f"image/{fmt}"
        )

        assert response.status_code == 400, response.text
        assert response.json()["error"]["code"] == "IMAGE_ANIMATED"
        assert storage.objects == {}

    async def test_a_long_animation_is_refused_too(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        product_id: str,
        storage: InMemoryStorage,
    ) -> None:
        written = animated_webp((64, 48), 3)
        parts = riff_chunks(written, 12, len(written))
        frame = next(p for f, p in parts if f == b"ANMF")
        head = [(f, p) for f, p in parts if f != b"ANMF"]
        original = webp_from_chunks([*head, *[(b"ANMF", frame)] * 3_000])

        response = await _upload(
            client, headers, product_id, data=original, filename="p.webp", content_type="image/webp"
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "IMAGE_ANIMATED"
        assert storage.objects == {}

    async def test_an_animation_that_is_also_too_large_is_told_it_is_animated(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        product_id: str,
        storage: InMemoryStorage,
    ) -> None:
        """Exporting a smaller one would still be refused, so that is the answer
        that helps - not the resolution one."""
        png = header_only_png(8_000, 8_000)
        data = png_after_header(png, png_chunk(b"acTL", struct.pack(">II", 2, 0)))
        with pytest.raises(ValidationError) as resolution:
            validate_image(header_only_png(8_000, 8_000), None)
        assert resolution.value.code == "IMAGE_TOO_MANY_PIXELS"  # the premise

        response = await _upload(client, headers, product_id, data=data)

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "IMAGE_ANIMATED"
        assert storage.objects == {}

    async def test_a_cut_animation_is_unreadable_not_animated(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        product_id: str,
        storage: InMemoryStorage,
    ) -> None:
        """The check comes after the structure has been verified: a file that is
        not a whole image is INVALID_IMAGE, whatever it announced."""
        response = await _upload(client, headers, product_id, data=animated_png((64, 48), 2)[:-11])

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_IMAGE"
        assert storage.objects == {}

    @pytest.mark.parametrize("size", ANIMATION_SIZES.values(), ids=ANIMATION_SIZES)
    async def test_an_apng_of_one_frame_is_still_stored(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        product_id: str,
        storage: InMemoryStorage,
        size: tuple[int, int],
    ) -> None:
        """Nothing moves, so there is nothing to refuse. It still walks the
        byte-level allowlist (acTL, fcTL, fdAT are kept chunks)."""
        original = one_frame_apng(size)
        assert b"acTL" in png_chunk_types(original)
        with Image.open(io.BytesIO(original)) as probe:
            assert probe.n_frames == 1  # type: ignore[attr-defined]

        response = await _upload(client, headers, product_id, data=original)

        assert response.status_code == 201, response.text
        stored = only_object(storage)
        assert pixels(stored)[1][0] <= size[0]  # it decodes
        if size[0] <= MAX_STORED_EDGE:
            assert stored == original  # walked, and nothing in it to strip

    @pytest.mark.parametrize("size", ANIMATION_SIZES.values(), ids=ANIMATION_SIZES)
    async def test_an_animated_webp_of_one_frame_is_still_stored(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        product_id: str,
        storage: InMemoryStorage,
        size: tuple[int, int],
    ) -> None:
        original = one_frame_animated_webp(size)
        top = riff_chunks(original, 12, len(original))
        assert [f for f, _ in top].count(b"ANMF") == 1
        assert top[0][1][0] & 0x02  # VP8X says animated
        with Image.open(io.BytesIO(original)) as probe:
            assert probe.n_frames == 1  # type: ignore[attr-defined]

        response = await _upload(
            client, headers, product_id, data=original, filename="p.webp", content_type="image/webp"
        )

        assert response.status_code == 201, response.text
        stored = only_object(storage)
        assert pixels(stored)[1][0] <= size[0]  # it decodes
        if size[0] <= MAX_STORED_EDGE:
            assert stored == original


class TestOnlyChunksKnownToBeHarmlessAreStored:
    """An allowlist, not a denylist: the chunks that can carry an identity are an
    open set, the ones that say how to show the picture are a short closed one."""

    @staticmethod
    async def _store(
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
        data: bytes,
        fmt: str,
    ) -> bytes:
        response = await _upload(
            client, headers, product_id, data=data, filename=f"p.{fmt}", content_type=f"image/{fmt}"
        )
        assert response.status_code == 201, response.text
        return only_object(storage)

    def test_a_png_keeps_what_shows_the_picture_and_nothing_that_names_its_maker(self) -> None:
        written = encode(patterned((120, 80)), "PNG", icc_profile=ICC_PROFILE, dpi=(300, 300))
        gamma = png_chunk(b"gAMA", struct.pack(">I", 45455))
        original = png_with_identity(png_after_header(written, gamma))
        assert set(PNG_IDENTITY) <= set(png_chunk_types(original))

        stored = shrink_to_fit(original, "PNG")

        kinds = png_chunk_types(stored)
        assert not set(PNG_IDENTITY) & set(kinds)
        assert {b"iCCP", b"pHYs", b"gAMA"} <= set(kinds)
        # Every kept chunk is the source's own bytes - CRC included, in order.
        expected = [c for c in png_chunks(original) if c[4:8] not in PNG_IDENTITY]
        assert png_chunks(stored) == expected
        for secret in PNG_IDENTITY.values():
            assert secret not in stored
        assert pixels(stored) == pixels(original)

    def test_a_png_made_only_of_known_chunks_is_stored_byte_for_byte(self) -> None:
        clean = encode(patterned((64, 48)), "PNG", icc_profile=ICC_PROFILE, dpi=(72, 72))

        assert shrink_to_fit(clean, "PNG") == clean

    def test_an_animated_png_keeps_every_frame(self) -> None:
        """The strip walks the animation chunks and must not flatten them. Called
        on `shrink_to_fit` directly: `validate_image` refuses a file of three frames
        (A-101), so this is the walker guarantee, which the one-frame APNG that does
        get through relies on (`TestAnimatedImagesAreRefused`)."""
        first, *rest = three_frames()
        written = encode(first, "PNG", save_all=True, append_images=rest)
        assert {b"acTL", b"fcTL", b"fdAT"} <= set(png_chunk_types(written))
        original = png_with_identity(written)

        stored = shrink_to_fit(original, "PNG")

        assert not set(PNG_IDENTITY) & set(png_chunk_types(stored))
        assert png_chunks(stored) == png_chunks(written)
        assert len(animation_frames(stored)) == 3
        assert animation_frames(stored) == animation_frames(original)

    def test_a_png_above_the_edge_whose_re_encode_is_no_smaller_is_stored_stripped(self) -> None:
        """The stripped original is what the re-encode is compared with and what
        is kept when the re-encode does not beat it - so it is the one that must
        not carry the chunks. A repeating ramp compresses well as drawn and badly
        once the resize has smoothed it."""
        original = png_with_identity(encode(patterned((1700, 40), "L"), "PNG"))
        stripped = storage_module._strip_png(original)
        with Image.open(io.BytesIO(original)) as probe:
            probe.thumbnail((MAX_STORED_EDGE, MAX_STORED_EDGE), Image.Resampling.LANCZOS)
            assert len(encode(probe, "PNG")) >= len(stripped)  # the premise

        stored = shrink_to_fit(original, "PNG")

        assert stored == stripped
        assert not set(PNG_IDENTITY) & set(png_chunk_types(stored))

    def test_a_webp_keeps_what_shows_the_picture_and_nothing_that_names_its_maker(self) -> None:
        written = encode(
            patterned((200, 100)),
            "WEBP",
            lossless=True,
            exif=exif_bytes(gps=True, make="Acme"),
            xmp=b"<x:xmpmeta>secret</x:xmpmeta>",
            icc_profile=ICC_PROFILE,
        )
        original = webp_with_identity(written)
        assert set(WEBP_IDENTITY) <= {
            fourcc for fourcc, _ in riff_chunks(original, 12, len(original))
        }

        stored = shrink_to_fit(original, "WEBP")

        kept = riff_chunks(stored, 12, len(stored))
        assert [fourcc for fourcc, _ in kept] == [b"VP8X", b"ICCP", b"VP8L"]
        by_name = dict(kept)
        assert by_name[b"ICCP"] == ICC_PROFILE
        assert by_name[b"VP8L"] == dict(riff_chunks(written, 12, len(written)))[b"VP8L"]
        # EXIF and XMP are gone and so are their flags; the ICC flag stays.
        assert by_name[b"VP8X"][0] & 0x0C == 0
        assert by_name[b"VP8X"][0] & 0x20
        assert int.from_bytes(stored[4:8], "little") == len(stored) - 8
        for secret in (*WEBP_IDENTITY.values(), b"Acme"):
            assert secret not in stored
        assert pixels(stored) == pixels(original)

    def test_a_webp_with_alpha_keeps_its_alpha_chunk_and_flag(self) -> None:
        written = encode(patterned((120, 80), "RGBA"), "WEBP", quality=80)
        assert {b"VP8X", b"ALPH", b"VP8 "} <= {f for f, _ in riff_chunks(written, 12, len(written))}
        original = webp_with_identity(written)

        stored = shrink_to_fit(original, "WEBP")

        kept = riff_chunks(stored, 12, len(stored))
        assert [fourcc for fourcc, _ in kept] == [b"VP8X", b"ALPH", b"VP8 "]
        assert kept[0][1][0] & 0x10  # the alpha flag still has its chunk
        assert pixels(stored) == pixels(original)

    def test_an_animated_webp_keeps_its_frames_and_loses_what_is_inside_them(self) -> None:
        """An `ANMF` payload is a 16-byte frame header and then chunks of its own:
        the spec lets a frame carry unknown ones, so they are filtered there too.
        The walker is called directly: `validate_image` refuses three frames now
        (A-101), and one `ANMF` is walked the same way."""
        first, *rest = three_frames()
        written = encode(first, "WEBP", save_all=True, append_images=rest, lossless=True)
        top = riff_chunks(written, 12, len(written))
        assert [f for f, _ in top].count(b"ANMF") == 3
        flagged = [
            (fourcc, payload + riff_chunk(b"C2PA", b"frame-c2pa-secret"))
            if fourcc == b"ANMF"
            else (fourcc, payload)
            for fourcc, payload in top
        ]
        original = webp_from_chunks([*flagged, (b"C2PA", b"top-c2pa-secret")])
        assert len(animation_frames(original)) == 3

        stored = shrink_to_fit(original, "WEBP")

        kept = riff_chunks(stored, 12, len(stored))
        assert [f for f, _ in kept] == [f for f, _ in top]
        assert kept[0][1][0] & 0x02  # VP8X still says it is animated
        for (_, got), (_, sent) in zip(
            [c for c in kept if c[0] == b"ANMF"], [c for c in top if c[0] == b"ANMF"], strict=True
        ):
            assert got[:16] == sent[:16]  # position, size, duration, blend and dispose
            assert got[16:] == sent[16:]  # exactly the frame's own image data
        assert b"c2pa-secret" not in stored
        assert int.from_bytes(stored[4:8], "little") == len(stored) - 8
        assert animation_frames(stored) == animation_frames(written)

    @pytest.mark.parametrize("payload", [b"", b"\x00" * 15])
    def test_an_animation_frame_too_short_for_its_header_is_invalid_not_decoded(
        self, payload: bytes
    ) -> None:
        first, *rest = three_frames()
        written = encode(first, "WEBP", save_all=True, append_images=rest, lossless=True)
        broken = webp_from_chunks(
            [(f, payload if f == b"ANMF" else p) for f, p in riff_chunks(written, 12, len(written))]
        )

        with pytest.raises(ValidationError) as refused:
            storage_module._strip_webp(broken)

        assert refused.value.code == "INVALID_IMAGE"

    def test_a_frame_chunk_longer_than_its_frame_is_invalid_not_decoded(self) -> None:
        first, *rest = three_frames()
        written = encode(first, "WEBP", save_all=True, append_images=rest, lossless=True)
        lying = webp_from_chunks(
            [
                (f, p[:16] + b"VP8L" + (10_000).to_bytes(4, "little") + b"x" * 8)
                if f == b"ANMF"
                else (f, p)
                for f, p in riff_chunks(written, 12, len(written))
            ]
        )

        with pytest.raises(ValidationError) as refused:
            storage_module._strip_webp(lying)

        assert refused.value.code == "INVALID_IMAGE"

    # --- the chunk cap (A-075) ---
    # libwebp has no limit on how many chunks a file has, and `validate_image` is
    # as fast on 5 MiB of empty 8-byte ones (3 ms, the demuxer is C) as on none; the
    # walk is Python. More than the cap in total is refused, whichever level they
    # are on. The counts below are literals, not `_MAX_WEBP_CHUNKS`, so a test of
    # the cap does not follow the cap upwards.
    EMPTY_CHUNKS = 70_000

    @staticmethod
    def _animation() -> list[tuple[bytes, bytes]]:
        first, *rest = three_frames()
        written = encode(first, "WEBP", save_all=True, append_images=rest, lossless=True)
        return riff_chunks(written, 12, len(written))

    def _padded_webp(self, shape: str) -> bytes:
        empty = riff_chunk(b"zzzz", b"")
        assert len(empty) == 8
        if shape == "after the picture":
            written = encode(patterned((64, 48)), "WEBP", lossless=True)
            picture = riff_chunks(written, 12, len(written))
            return webp_from_chunks([*picture, *[(b"zzzz", b"")] * self.EMPTY_CHUNKS])
        parts = self._animation()
        frames = [p for f, p in parts if f == b"ANMF"]
        if shape == "inside the frames":
            # Each frame is under any sane cap on its own: only the sum is over.
            # Three frames: `validate_image` refuses it as animated (A-101), so
            # this shape reaches the walkers directly, not the upload.
            each = self.EMPTY_CHUNKS // len(frames) + 1
            padded = [(f, p + empty * each if f == b"ANMF" else p) for f, p in parts]
            return webp_from_chunks(padded)
        if shape == "inside the one frame":
            top = [(f, p) for f, p in parts if f != b"ANMF"]
            return webp_from_chunks([*top, (b"ANMF", frames[0] + empty * self.EMPTY_CHUNKS)])
        # Half in one frame, half at the top: neither level is over on its own.
        assert shape == "split between the levels"
        top = [(f, p) for f, p in parts if f != b"ANMF"]
        half = self.EMPTY_CHUNKS // 2
        body = [(b"ANMF", frames[0] + empty * half)] + [(b"zzzz", b"")] * half
        return webp_from_chunks([*top, *body])

    #: The shapes of one frame (or none) are what an upload can carry now.
    UPLOADABLE_SHAPES: ClassVar[list[str]] = [
        "after the picture",
        "inside the one frame",
        "split between the levels",
    ]
    SHAPES: ClassVar[list[str]] = [*UPLOADABLE_SHAPES, "inside the frames"]

    @pytest.mark.parametrize("shape", SHAPES)
    def test_a_webp_padded_with_empty_chunks_is_refused_by_count(self, shape: str) -> None:
        """The file is one libwebp accepts: the refusal is the walk's, by count, and
        not something the premise of the test gets from a broken file."""
        hostile = self._padded_webp(shape)
        assert len(hostile) < settings.max_image_bytes
        if shape in self.UPLOADABLE_SHAPES:
            assert validate_image(hostile, "image/webp")[0] == "WEBP"
        else:
            # Three frames: refused by `validate_image` as animated, so the premise
            # is Pillow's own parser, which is what the walk has to be cheaper than.
            with Image.open(io.BytesIO(hostile), formats=["WEBP"]) as probe:
                probe.verify()

        for walk in (storage_module._strip_webp, lambda data: shrink_to_fit(data, "WEBP")):
            with pytest.raises(ValidationError) as refused:
                walk(hostile)
            assert refused.value.code == "INVALID_IMAGE"

    @pytest.mark.parametrize("shape", UPLOADABLE_SHAPES)
    async def test_an_upload_padded_with_empty_chunks_is_a_400_and_stores_nothing(
        self,
        shape: str,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
    ) -> None:
        response = await _upload(
            client,
            headers,
            product_id,
            data=self._padded_webp(shape),
            filename="p.webp",
            content_type="image/webp",
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_IMAGE"
        assert not storage.objects

    def test_the_chunk_cap_counts_every_chunk_and_not_one_too_many(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A file of exactly `n` chunks passes at `n` and is refused at `n - 1`, so
        a legitimate file has nothing to fear from an off-by-one - and the chunks
        inside a frame are counted along with the file's."""
        parts = self._animation()
        clean = webp_from_chunks(parts)
        count = 8  # VP8X, ANIM, three ANMF, and the VP8L inside each
        assert count == len(parts) + sum(
            len(riff_chunks(p, 16, len(p))) for f, p in parts if f == b"ANMF"
        )

        monkeypatch.setattr(storage_module, "_MAX_WEBP_CHUNKS", count)
        assert storage_module._strip_webp(clean) == clean

        monkeypatch.setattr(storage_module, "_MAX_WEBP_CHUNKS", count - 1)
        with pytest.raises(ValidationError) as refused:
            storage_module._strip_webp(clean)
        assert refused.value.code == "INVALID_IMAGE"

    def test_the_walk_still_keeps_a_long_animation_whole(self) -> None:
        """One `ANMF` per frame and a picture chunk inside it: 3 000 frames are
        6 000 chunks, a tenth of the cap, and nothing of the animation is lost.
        This used to be an upload that was stored; `validate_image` refuses it now
        (A-101, `test_a_long_animation_is_refused_too`), so what stays pinned is the
        walker's own guarantee that the cap is far above a real animation."""
        parts = self._animation()
        frame = next(p for f, p in parts if f == b"ANMF")
        head = [(f, p) for f, p in parts if f != b"ANMF"]
        original = webp_from_chunks([*head, *[(b"ANMF", frame)] * 3_000])
        with Image.open(io.BytesIO(original)) as probe:
            assert probe.n_frames == 3_000  # type: ignore[attr-defined]

        stored = storage_module._strip_webp(original)

        assert stored == original  # nothing in it to strip
        with Image.open(io.BytesIO(stored)) as saved:
            assert saved.n_frames == 3_000  # type: ignore[attr-defined]

    def test_a_resized_webp_the_walk_refuses_is_stored_as_the_re_encode(self) -> None:
        """What still holds from A-059: a WebP that was decoded anyway (it is above
        the edge) has a clean re-encode, so the walk's refusal only costs the
        comparison with the stripped original."""
        written = encode(patterned((1700, 1000)), "WEBP", lossless=True, method=0)
        picture = riff_chunks(written, 12, len(written))
        padded = webp_from_chunks([*picture, *[(b"zzzz", b"")] * self.EMPTY_CHUNKS])
        with pytest.raises(ValidationError):  # the premise: the walk refuses it
            storage_module._strip_webp(padded)
        assert validate_image(padded, "image/webp")[0] == "WEBP"

        stored = shrink_to_fit(padded, "WEBP")

        with Image.open(io.BytesIO(stored)) as saved:
            assert max(saved.size) == MAX_STORED_EDGE
        assert b"zzzz" not in stored

    def test_a_jpeg_keeps_jfif_and_loses_the_thumbnail_extension_and_foreign_segments(
        self,
    ) -> None:
        written = encode(patterned((300, 200)), "JPEG", icc_profile=ICC_PROFILE)
        assert 0xE0 in jpeg_markers(written)  # the JFIF header
        original = jpeg_with_identity(written)
        assert {0xE0, 0xEB, 0xEE} <= set(jpeg_markers(original))

        stored = shrink_to_fit(original, "JPEG")

        markers = jpeg_markers(stored)
        assert markers == jpeg_markers(written)  # the JFIF and the ICC profile, no more
        assert b"JFIF\x00" in stored
        for secret in (b"JFXX", b"thumb-secret", b"c2pa-secret", b"Phone", b"app14-secret"):
            assert secret not in stored
        assert pixels(stored) == pixels(original)

    def test_a_jpeg_keeps_adobe_and_loses_an_app14_that_is_not_adobe(self) -> None:
        written = encode(patterned((200, 100), "CMYK"), "JPEG")
        assert b"Adobe" in written
        original = jpeg_with_identity(written)

        stored = shrink_to_fit(original, "JPEG")

        assert jpeg_markers(stored) == jpeg_markers(written)
        assert stored.count(b"Adobe") == 1
        assert b"Phone" not in stored
        assert pixels(stored) == pixels(original)

    # --- The JFIF thumbnail and what follows Adobe's 12 bytes (A-098) ---------

    @pytest.mark.parametrize("size", ["fits", "resized"])
    def test_a_jfif_thumbnail_is_not_stored(self, size: str) -> None:
        """APP0 `JFIF` is a header followed by an uncompressed RGB thumbnail of
        3*X*Y bytes - a small picture of the whole frame, which the public file
        would carry beside the one that was cropped."""
        thumbnail = b"thumbsecret!" * 3  # 4x3 RGB: 36 bytes
        written = encode(patterned((300, 200) if size == "fits" else (1700, 400)), "JPEG")
        original = jpeg_with_payload(written, 0xE0, JFIF_HEADER + bytes((4, 3)) + thumbnail)
        assert thumbnail in original

        stored = shrink_to_fit(original, "JPEG")

        assert thumbnail not in stored
        segment = jpeg_segment(stored, 0xE0)
        # Length 16 and a 0x0 thumbnail, whether the file was stripped or (the
        # larger one) re-encoded by Pillow, whose writer makes a header of its own.
        assert segment[:4] == b"\xff\xe0\x00\x10"
        assert segment[4:9] == b"JFIF\x00"
        assert segment[-2:] == b"\x00\x00"
        if size == "fits":  # stripped, not re-encoded: the same header and pixels
            assert segment == b"\xff\xe0\x00\x10" + JFIF_HEADER + b"\x00\x00"
            assert pixels(stored) == pixels(original)

    def test_a_jfif_header_with_a_thumbnail_size_and_no_thumbnail_is_reset(self) -> None:
        written = encode(patterned((300, 200)), "JPEG")
        original = jpeg_with_payload(written, 0xE0, JFIF_HEADER + bytes((9, 9)))

        stored = shrink_to_fit(original, "JPEG")

        assert jpeg_segment(stored, 0xE0) == b"\xff\xe0\x00\x10" + JFIF_HEADER + b"\x00\x00"

    def test_adobe_keeps_its_twelve_bytes_with_the_transform_and_nothing_after(self) -> None:
        """The transform byte says how to read CMYK (2 is YCCK); what follows the
        12 bytes is nobody's."""
        written = encode(patterned((200, 100), "CMYK"), "JPEG")
        adobe = jpeg_segment(written, 0xEE)
        assert adobe[:2] + adobe[4:9] == b"\xff\xeeAdobe"
        header = adobe[4:16][:11] + b"\x02"  # `Adobe`, version, two flags, transform
        original = jpeg_with_payload(written, 0xEE, header + b"adobe-secret")
        assert b"adobe-secret" in original

        stored = shrink_to_fit(original, "JPEG")

        assert jpeg_segment(stored, 0xEE) == b"\xff\xee\x00\x0e" + header
        assert b"adobe-secret" not in stored
        assert pixels(stored) == pixels(original)

    @pytest.mark.parametrize("mode", ["RGB", "CMYK"])
    def test_a_jpeg_whose_segments_are_already_minimal_comes_back_byte_for_byte(
        self, mode: str
    ) -> None:
        written = encode(patterned((200, 100), mode), "JPEG", icc_profile=ICC_PROFILE)
        if mode == "RGB":  # Pillow writes a JFIF header for RGB and Adobe for CMYK
            jfif = jpeg_segment(written, 0xE0)
            assert (jfif[:4], jfif[-2:]) == (b"\xff\xe0\x00\x10", b"\x00\x00")  # no thumbnail
        else:
            assert jpeg_segment(written, 0xEE)[:4] == b"\xff\xee\x00\x0e"

        assert shrink_to_fit(written, "JPEG") == written

    def test_a_jfif_or_adobe_segment_too_short_to_hold_a_thumbnail_is_kept_as_it_is(self) -> None:
        """A payload under 14 bytes has no thumbnail size, so there is nothing to
        reset or cut - and refusing it would turn away a file Pillow reads."""
        written = encode(patterned((200, 100), "CMYK"), "JPEG")
        short_jfif = JFIF_HEADER[:-3]  # 9 bytes: `JFIF\0`, version, units, one density byte
        short_adobe = b"Adobe\x00\x64\x00\x00"
        original = jpeg_with_segments(written, (0xE0, short_jfif), (0xEE, short_adobe))

        stored = storage_module._strip_jpeg(original)

        assert jpeg_segment(stored, 0xE0) == b"\xff\xe0\x00\x0b" + short_jfif
        assert b"\xff\xee\x00\x0b" + short_adobe in stored

    @pytest.mark.parametrize("fmt", ["png", "webp", "jpeg"])
    async def test_an_upload_is_stored_without_the_chunks_it_carried(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        storage: InMemoryStorage,
        product_id: str,
        fmt: str,
    ) -> None:
        if fmt == "png":
            original = png_with_identity(
                encode(patterned((120, 80)), "PNG", icc_profile=ICC_PROFILE)
            )
            secrets = tuple(PNG_IDENTITY.values())
        elif fmt == "webp":
            original = webp_with_identity(
                encode(patterned((120, 80)), "WEBP", lossless=True, icc_profile=ICC_PROFILE)
            )
            secrets = tuple(WEBP_IDENTITY.values())
        else:
            original = jpeg_with_identity(
                encode(patterned((120, 80)), "JPEG", icc_profile=ICC_PROFILE)
            )
            secrets = (b"JFXX", b"thumb-secret", b"c2pa-secret", b"app14-secret")
        assert all(secret in original for secret in secrets)

        stored = await self._store(client, headers, storage, product_id, original, fmt)

        for secret in secrets:
            assert secret not in stored
        with Image.open(io.BytesIO(stored)) as saved:
            assert saved.info["icc_profile"] == ICC_PROFILE
        assert pixels(stored) == pixels(original)


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
