"""A request body is refused before it is read, not after it is parsed.

Starlette reads a JSON body whole and Pydantic parses it before `max_length` can
object, so a 24 MB body from a stranger cost a worker about 250 MB - and the
answer was a 400. On a 512 MB instance with two workers that is an outage from
one request. The limit sits in front of all of that.
"""

from collections.abc import AsyncIterator

import httpx
from app.core.config import settings

LIMIT = settings.max_request_body_bytes
ERRORS = "/api/v1/client-errors"
IMAGES = "/api/v1/admin/products/00000000-0000-0000-0000-000000000001/images"


def _body(size: int) -> bytes:
    return b'{"message":"' + b"a" * (size - 14) + b'"}'


async def test_a_body_over_the_limit_is_refused_by_its_declared_length(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        ERRORS, content=_body(LIMIT + 1), headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


async def test_a_chunked_body_over_the_limit_is_refused_too(client: httpx.AsyncClient) -> None:
    """No Content-Length to check, so the bytes are counted as they arrive."""

    async def chunks() -> AsyncIterator[bytes]:
        for _ in range((LIMIT // 8192) + 4):
            yield b"a" * 8192

    response = await client.post(
        ERRORS, content=chunks(), headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


async def test_a_body_at_the_limit_still_reaches_the_route(client: httpx.AsyncClient) -> None:
    response = await client.post(
        ERRORS, content=_body(LIMIT), headers={"Content-Type": "application/json"}
    )

    # Whatever the route thinks of it, it was allowed to think.
    assert response.status_code != 413


async def test_an_image_may_be_as_large_as_the_image_limit_allows(
    client: httpx.AsyncClient,
) -> None:
    """The upload route is the one place a megabytes-long body is legitimate."""
    boundary = "x"
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="a.jpg"\r\n'
            "Content-Type: image/jpeg\r\n\r\n"
        ).encode()
        + b"a" * (LIMIT * 2)
        + f"\r\n--{boundary}--\r\n".encode()
    )
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}

    allowed = await client.post(IMAGES, content=body, headers=headers)
    too_big = await client.post(
        IMAGES, content=b"a" * (settings.max_image_bytes + 70 * 1024), headers=headers
    )

    assert allowed.status_code != 413  # refused for lack of an admin, not for size
    assert too_big.status_code == 413


def _assert_image_too_large(response: httpx.Response) -> None:
    assert response.status_code == 413, response.text
    error = response.json()["error"]
    assert error["code"] == "IMAGE_TOO_LARGE"
    # The panel turns this into "photo is over N MB"; it is the same shape the
    # upload route's own IMAGE_TOO_LARGE carries.
    assert error["details"] == {"maxBytes": settings.max_image_bytes}


async def test_an_oversized_photo_is_told_it_is_too_large_by_declared_length(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        IMAGES,
        content=b"a" * (settings.max_image_bytes + 70 * 1024),
        headers={"Content-Type": "multipart/form-data; boundary=x"},
    )

    _assert_image_too_large(response)


async def test_an_oversized_chunked_photo_is_told_it_is_too_large_too(
    client: httpx.AsyncClient,
) -> None:
    # Valid multipart framing first, or the form parser objects to the bytes
    # before the limit is reached.
    opening = (
        b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.jpg"\r\n'
        b"Content-Type: image/jpeg\r\n\r\n"
    )

    async def chunks() -> AsyncIterator[bytes]:
        yield opening
        for _ in range((settings.max_image_bytes + 70 * 1024) // 8192 + 1):
            yield b"a" * 8192

    response = await client.post(
        IMAGES, content=chunks(), headers={"Content-Type": "multipart/form-data; boundary=x"}
    )

    _assert_image_too_large(response)
