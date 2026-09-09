"""სტრუქტურირებული JSON-ლოგები და request_id-ის გავრცელება.

თითო მოთხოვნა = ერთი ხაზი: method, path, status, ხანგრძლივობა, request_id.
ავტორიზაციის მარშრუტებზე სხეული არასდროს ილოგება.
"""

import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"

# ამ პრეფიქსებზე მოთხოვნის სხეული და query არასდროს არ ილოგება
SENSITIVE_PATH_PREFIXES = ("/api/v1/auth",)


class JsonFormatter(logging.Formatter):
    """ლოგს ერთხაზიან JSON-ად აქცევს — რომ Grafana/Loki-მ პარსოს."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if extra := getattr(record, "extra_fields", None):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    # uvicorn-ის საკუთარი access-ლოგი ჩვენსას დუბლირებს
    logging.getLogger("uvicorn.access").disabled = True


access_logger = logging.getLogger("voltbox.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """request_id-ს ანიჭებს, დროს ზომავს და ერთ ხაზს ლოგავს."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:16]
        request.state.request_id = request_id

        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)

        response.headers[REQUEST_ID_HEADER] = request_id

        is_sensitive = request.url.path.startswith(SENSITIVE_PATH_PREFIXES)
        access_logger.info(
            "request",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query": "" if is_sensitive else str(request.url.query),
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                }
            },
        )
        return response
