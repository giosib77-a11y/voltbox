"""Product images.

What it covers: uploads are validated by decoding, not by trusting the filename
or the declared MIME type; the one-primary-per-product rule survives the order
in which SQLAlchemy flushes; and deleting an image never breaks the thumbnail of
a past order.

Runs against the in-memory storage backend, so image handling is fully covered
without Supabase credentials.
"""

import io
import os
import struct
import subprocess
import sys
import uuid
import zlib

import httpx
import pytest
from app.core.config import settings
from app.core.errors import ValidationError
from app.db.models import ROLE_ADMIN, OrderItem, ProductImage
from app.main import app
from app.services.storage import (
    DECODE_COST,
    MAX_STORED_EDGE,
    InMemoryStorage,
    SupabaseStorage,
    get_storage,
    shrink_to_fit,
    validate_image,
)
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

ADMIN = "/api/v1/admin"


#: One flat colour per mode. Decode memory follows the dimensions and the
#: format, never the picture, so a solid image measures the same as a photograph.
COLOURS = {"RGB": (200, 40, 10), "RGBA": (200, 40, 10, 128), "CMYK": (10, 40, 200, 5), "L": 120}


def image_bytes(
    fmt: str = "PNG", size: tuple[int, int] = (32, 32), mode: str = "RGB", **options: object
) -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, COLOURS[mode]).save(buffer, format=fmt, **options)
    return buffer.getvalue()


def header_only_png(width: int, height: int) -> bytes:
    """A PNG that declares a size and carries no picture.

    A real image of these dimensions cannot be built - that is the whole point of
    a decompression bomb - and `Image.open` only ever reads the header, so a few
    hand-written chunks are the honest way to present one.
    """

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b""))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def storage() -> InMemoryStorage:
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
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str, **kwargs: object
) -> httpx.Response:
    data = kwargs.pop("data", None) or image_bytes()
    name = kwargs.pop("filename", "photo.png")
    content_type = kwargs.pop("content_type", "image/png")
    return await client.post(
        f"{ADMIN}/products/{product_id}/images",
        headers=headers,
        files={"file": (name, data, content_type)},
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
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str, monkeypatch
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
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str, monkeypatch
) -> None:
    from app.core.config import settings

    # A small file can decode to an enormous bitmap, and the decode is what
    # allocates - so the budget is memory, checked before anything is decoded.
    monkeypatch.setattr(settings, "max_image_decode_bytes", 100)

    response = await _upload(client, headers, product_id, data=image_bytes(size=(64, 64)))

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
        monkeypatch.setattr(settings, "supabase_service_role_key", "a-key", raising=False)
        monkeypatch.setattr(settings, "app_env", "production", raising=False)

        assert isinstance(get_storage(), SupabaseStorage)

    @pytest.mark.parametrize("env", ["development", "test"])
    def test_falls_back_locally(self, monkeypatch: pytest.MonkeyPatch, env: str) -> None:
        monkeypatch.setattr(settings, "supabase_project_ref", "", raising=False)
        monkeypatch.setattr(settings, "supabase_service_role_key", "", raising=False)
        monkeypatch.setattr(settings, "app_env", env, raising=False)

        assert isinstance(get_storage(), InMemoryStorage)

    @pytest.mark.parametrize("env", ["production", "staging"])
    def test_refuses_to_fall_back_in_a_deployment(
        self, monkeypatch: pytest.MonkeyPatch, env: str
    ) -> None:
        monkeypatch.setattr(settings, "supabase_project_ref", "", raising=False)
        monkeypatch.setattr(settings, "supabase_service_role_key", "", raising=False)
        monkeypatch.setattr(settings, "app_env", env, raising=False)

        with pytest.raises(RuntimeError, match="Object storage is not configured"):
            get_storage()

    def test_refuses_when_only_half_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ref without a key is the shape a half-filled .env actually has."""
        monkeypatch.setattr(settings, "supabase_project_ref", "somewhere", raising=False)
        monkeypatch.setattr(settings, "supabase_service_role_key", "", raising=False)
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
        monkeypatch.setattr(settings, "supabase_service_role_key", "a-real-key", raising=False)
        monkeypatch.setattr(settings, "app_env", "test", raising=False)

        assert isinstance(get_storage(), InMemoryStorage)

    def test_development_still_uses_the_configured_bucket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Uploading real product images locally is the point of configuring it."""
        monkeypatch.setattr(settings, "supabase_project_ref", "a-real-project", raising=False)
        monkeypatch.setattr(settings, "supabase_service_role_key", "a-real-key", raising=False)
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
        """Re-encoding a small image only loses quality."""
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


def largest_that_fits(path: str) -> tuple[int, int]:
    """The biggest 4:3 image of `path` the decode budget still accepts."""
    fixed, per_pixel = DECODE_COST[path]
    pixels = (settings.max_image_decode_bytes - fixed) // per_pixel
    height = int((pixels * 3 / 4) ** 0.5)
    return (height * 4 // 3, height)


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
        """MAX_STORED_EDGE is 1600, so this one is kept exactly as it arrived.

        The tightest of the limits is still above 1600x1600 - if it were not, an
        upload could be refused for the memory of a resize that never happens.
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

        assert largest <= Image.MAX_IMAGE_PIXELS


#: Measures one decode in a process of its own. Pillow allocates its bitmaps in C
#: and libwebp allocates its canvases outside Pillow, so tracemalloc sees neither
#: and only the operating system's own counter is the truth here.
PEAK_DECODE = """
import os, sys

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
    import resource
    with open("/proc/self/statm") as handle:
        current = int(handle.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    return current, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024

data = sys.stdin.buffer.read()
from app.services.storage import shrink_to_fit, validate_image

before, _ = memory()
image_format, _ = validate_image(data, None)
shrink_to_fit(data, image_format)
_, peak = memory()
print(peak - before)
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
    return int(result.stdout)


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
