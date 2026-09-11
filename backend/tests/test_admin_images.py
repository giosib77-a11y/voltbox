"""Product images.

What it covers: uploads are validated by decoding, not by trusting the filename
or the declared MIME type; the one-primary-per-product rule survives the order
in which SQLAlchemy flushes; and deleting an image never breaks the thumbnail of
a past order.

Runs against the in-memory storage backend, so image handling is fully covered
without Supabase credentials.
"""

import io
import uuid

import httpx
import pytest
from app.db.models import ROLE_ADMIN, OrderItem, ProductImage
from app.main import app
from app.services.storage import InMemoryStorage, get_storage
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_brand, make_category, make_product, make_user

ADMIN = "/api/v1/admin"


def image_bytes(fmt: str = "PNG", size: tuple[int, int] = (32, 32)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 40, 10)).save(buffer, format=fmt)
    return buffer.getvalue()


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


async def test_upload_rejects_a_decompression_bomb_by_pixel_count(
    client: httpx.AsyncClient, headers: dict[str, str], product_id: str, monkeypatch
) -> None:
    from app.core.config import settings

    # A small file can decode to an enormous bitmap; only a pixel check catches it.
    monkeypatch.setattr(settings, "max_image_pixels", 100)

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
