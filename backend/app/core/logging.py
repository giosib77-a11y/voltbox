"""სტრუქტურირებული JSON-ლოგები და request_id-ის გავრცელება.

თითო მოთხოვნა = ერთი ხაზი: method, path, status, ხანგრძლივობა, request_id, client.
`client` კლიენტის IP-ის ფსევდონიმია (HMAC), არა თვით IP — ნედლი IP ლოგში არსად ჩანს.
ავტორიზაციის მარშრუტებზე სხეული არასდროს ილოგება.
"""

import hashlib
import hmac
import json
import logging
import re
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

REQUEST_ID_HEADER = "X-Request-ID"

#: What an incoming X-Request-ID may look like to be kept. The value is echoed in
#: a response header and written into every log line of the request, so it is
#: input from outside going into the log: a 300-character value, markup, or a
#: control character has no business there. Anything else is replaced with a
#: generated id (16 hex chars), and the request goes on as normal.
#: What still holds: a caller's own trace id (a UUID, a hex id, a `trace-123`
#: style id) fits and is carried through, so tracing from the browser to the log
#: keeps working. Matched with `fullmatch`: a trailing newline would pass `$`.
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9-]{8,64}")


def request_id_from(header_value: str | None) -> str:
    """The incoming id if it is a well-formed one, else a fresh one."""
    if header_value is not None and REQUEST_ID_PATTERN.fullmatch(header_value):
        return header_value
    return uuid.uuid4().hex[:16]


#: What the access line's `client` field says when the request has no client
#: address at all (an ASGI server that did not report one). Not an empty string
#: and not a hash of one: a fixed marker is visibly "unknown", and cannot be
#: mistaken for a real, shared bucket.
NO_CLIENT = "-"

#: Purpose label of the log pseudonym's key. The key is HMAC(JWT_SECRET, label),
#: so the value that keys the log is neither the JWT signing key nor reusable as
#: one, and a second purpose would use a second label.
CLIENT_LOG_KEY_LABEL = b"voltbox:access-log:client:v1"


@lru_cache(maxsize=4)
def _client_log_key(jwt_secret: str) -> bytes:
    """The pseudonym key for one JWT_SECRET, derived once per distinct secret.

    Keyed on the secret's value rather than computed at import: Settings may be
    rebuilt (tests do, and a rotated secret is a restart), and the key then
    follows it instead of going stale. Per request this is a cache lookup.
    """
    return hmac.new(jwt_secret.encode(), CLIENT_LOG_KEY_LABEL, hashlib.sha256).digest()


def client_pseudonym(host: str | None) -> str:
    """12 hex chars standing for a client address, stable across requests.

    Why not the address: an IP is personal data and the log is read by more
    people than the database. Why not a plain hash of it: an IPv4 address has
    only 2**32 values, so sha256(ip) is reversed by trying all of them; the
    keyed HMAC cannot be without the key. The 48 bits kept are plenty to tell
    clients apart in a log and give no way back.

    What still holds: the same address under the same JWT_SECRET always gives
    the same value, so an operator can see whether the rate limiter - which keys
    on this same `request.client.host` - is looking at many clients or one. A
    rotated JWT_SECRET changes every value, which is acceptable for a log.
    """
    if host is None:
        return NO_CLIENT
    key = _client_log_key(settings.jwt_secret.get_secret_value())
    return hmac.new(key, host.encode(), hashlib.sha256).hexdigest()[:12]


#: Postgres names the offending value when a constraint is violated:
#:
#:     DETAIL:  Key (email)=(nino@example.ge) already exists.
#:
#: That line is part of the database's own error message, so it survives
#: SQLAlchemy's hide_parameters and lands in the traceback the error handler
#: logs. The column is the half worth keeping; the value is a customer's email,
#: phone or order number. A NOT NULL or CHECK violation quotes the whole row
#: instead: `DETAIL:  Failing row contains (<every column>)`.
#:
#: The value is cut to the END OF THE LINE, not to the next `)`: a value may
#: contain `)` (`Key (name)=(Foo) Bar) already exists.`), and so does the column
#: expression (`Key (lower(email))=(a@b.com)`), and stopping at the first `)`
#: would leave the rest of the value in the log. The price is that the words
#: after the value (`already exists.`) go too; the constraint name in the line
#: above still says what kind of violation it was.
#: What still holds: only the line the DETAIL starts on is cut. A value with a
#: newline in it (a free-text `notes` column in a failing row) continues on the
#: following lines, and those are not scrubbed.
PG_DETAIL_VALUE = re.compile(r"(Key \(.*?\)=\(|Failing row contains \()[^\n]*")


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
            # Scrubbed too: a library can log `%s` of an exception, and then the
            # DETAIL line is in the message, not in a traceback.
            "message": scrub(record.getMessage()),
        }
        if extra := getattr(record, "extra_fields", None):
            payload.update(extra)
        if record.exc_info:
            # Scrubbed: a traceback is not a neutral object. See `scrub`.
            payload["exception"] = scrub(self.formatException(record.exc_info))
        elif record.exc_text:
            payload["exception"] = scrub(record.exc_text)
        return json.dumps(payload, ensure_ascii=False)


#: Loggers whose handlers the server wires up by itself, before the application
#: starts, and which therefore never pass through JsonFormatter on their own:
#:
#: - `uvicorn.error` and `gunicorn.error`: under gunicorn, UvicornWorker gives
#:   `uvicorn.error` gunicorn's own handlers and sets propagate=False; gunicorn
#:   does the same for its error logger. This is where Starlette's re-raised
#:   "Exception in ASGI application" lands after a 500.
#: - `uvicorn`: under plain `uvicorn`, its dictConfig gives this parent logger a
#:   handler of its own, and `uvicorn.error` propagates into it.
SERVER_LOGGERS = ("uvicorn", "uvicorn.error", "gunicorn.error")


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    # The server's own loggers go through the same handler, so the one scrub in
    # JsonFormatter covers them - a traceback of an unhandled error was written
    # by uvicorn.error as plain text, with Postgres's `DETAIL: Key (email)=(...)`
    # in it. Run from the lifespan, i.e. after the server wired them, so this
    # has to undo that rather than precede it. The master process never runs
    # this, and what it logs (workers starting and exiting) carries no customer
    # data.
    for name in SERVER_LOGGERS:
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True
    # uvicorn-ის საკუთარი access-ლოგი ჩვენსას დუბლირებს
    logging.getLogger("uvicorn.access").disabled = True


access_logger = logging.getLogger("voltbox.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """request_id-ს ანიჭებს, დროს ზომავს და ერთ ხაზს ლოგავს."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request_id_from(request.headers.get(REQUEST_ID_HEADER))
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
                    # The very value the rate limiter keys on (slowapi's
                    # get_remote_address), so this shows what the limiter sees.
                    "client": client_pseudonym(request.client.host if request.client else None),
                    "query": "" if is_sensitive else str(request.url.query),
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            },
        )
