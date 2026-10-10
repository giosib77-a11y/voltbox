"""Refuse an oversized request body before anything reads it.

What it does: answers 413 when a request body is larger than the limit for its
route, judged by Content-Length when there is one and by counting the bytes as
they arrive when there is not (chunked).
Where it fits: added in app/main.py just inside the CORS and request-context
middleware, so the 413 carries CORS headers and an access-log line.

Why it exists: Starlette reads a JSON body whole and Pydantic parses it before a
`max_length` can object. Measured, a 24 MB body from an unauthenticated caller
cost a worker about 250 MB and the answer was a 400. Rate limits do not help,
because one request is enough; on a 512 MB instance with two workers this is a
way to take the API down, so the check runs before the body is read at all.

Written as plain ASGI rather than BaseHTTPMiddleware: the latter reads the
request through its own wrapper, which is the layer that has to be in front.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body

#: Room for the multipart framing around a file: boundaries, the part headers and
#: the other form fields. An image over `max_image_bytes` but inside this reaches
#: the upload route, which refuses it with 400 IMAGE_TOO_LARGE. Anything past it is
#: refused here, as 413, but with the same IMAGE_TOO_LARGE code and `maxBytes`
#: details (see `BodyLimit`), so the panel shows the same "photo is over N MB"
#: whichever of the two answers.
MULTIPART_OVERHEAD = 64 * 1024


@dataclass(frozen=True)
class BodyLimit:
    """A route's size limit and the error that answers a body over it."""

    max_bytes: int
    code: str = "PAYLOAD_TOO_LARGE"
    message: str = "Request body is too large"
    details: Any = None

    @property
    def error(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, limit_for: Callable[[Scope], BodyLimit]) -> None:
        self.app = app
        self.limit_for = limit_for

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = self.limit_for(scope)
        declared = _declared_length(scope)
        if declared is not None and declared > limit.max_bytes:
            await _refuse(send, limit)
            return

        received = 0

        async def counted_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit.max_bytes:
                    # FastAPI's own HTTPException, because it is the one kind
                    # its body reader lets through: any other exception raised
                    # while reading is rewritten to a 400 "error parsing the
                    # body". The app's HTTP error handler answers it, as 413,
                    # with the code and details carried in `detail`.
                    raise HTTPException(status_code=413, detail=limit.error)
            return message

        await self.app(scope, counted_receive, send)


def _declared_length(scope: Scope) -> int | None:
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _refuse(send: Send, limit: BodyLimit) -> None:
    body = json.dumps(
        error_body(limit.code, limit.message, limit.details), separators=(",", ":")
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
