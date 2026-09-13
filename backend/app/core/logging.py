"""სტრუქტურირებული JSON-ლოგები და request_id-ის გავრცელება.

თითო მოთხოვნა = ერთი ხაზი: method, path, status, ხანგრძლივობა, request_id.
ავტორიზაციის მარშრუტებზე სხეული არასდროს ილოგება.
"""

import json
import logging
import re
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"

#: Postgres names the offending value when a constraint is violated:
#:
#:     DETAIL:  Key (email)=(nino@example.ge) already exists.
#:
#: That line is part of the database's own error message, so it survives
#: SQLAlchemy's hide_parameters and lands in the traceback the error handler
#: logs. The column is the half worth keeping; the value is a customer's email,
#: phone or order number.
PG_DETAIL_VALUE = re.compile(r"(Key \([^)]*\)=\()[^)]*\)")


def scrub(text: str) -> str:
    """Remove the values a database error quotes back, keeping the column."""
    return PG_DETAIL_VALUE.sub(r"\1…)", text)


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
            # Scrubbed: a traceback is not a neutral object. See `scrub`.
            payload["exception"] = scrub(self.formatException(record.exc_info))
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
        try:
            response = await call_next(request)
        except Exception:
            # Not a swallow - it is re-raised on the next line, and
            # ServerErrorMiddleware still turns it into the 500. Without this
            # the one request worth seeing was the one that never appeared:
            # an exception passes straight through here, so a crash left no
            # access line at all and a spike of 500s was invisible in the log
            # everybody reads first. The traceback itself is written by the
            # handler in core/errors.py, under the same request_id.
            self._log(request, request_id, 500, started)
            raise

        response.headers[REQUEST_ID_HEADER] = request_id
        self._log(request, request_id, response.status_code, started)
        return response

    @staticmethod
    def _log(request: Request, request_id: str, status: int, started: float) -> None:
        is_sensitive = request.url.path.startswith(SENSITIVE_PATH_PREFIXES)
        access_logger.info(
            "request",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query": "" if is_sensitive else str(request.url.query),
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            },
        )
