"""Response headers that harden what a browser will do with an API reply.

What it does: sets the four headers that mean something for a JSON API, plus
HSTS once the API is actually served over TLS.
Where it fits: added in app/main.py, outermost of the middleware stack so the
headers reach error responses too - a 500 is exactly when a browser should not
be improvising.

Why so few: most of the header advice written for web pages does not apply to
an endpoint that only ever returns JSON. A Content-Security-Policy governs what
a *document* may load, and these responses are not documents; the frontend is a
separate static deployment and needs its own policy there, set by whatever
serves the HTML. What is left is the set below, and each earns its place:

  nosniff          stops a browser deciding a JSON body is really HTML and
                   rendering it. That is the one way a pure API response turns
                   into script execution, and the reply carries user data.
  frame-ancestors  the API has no UI to frame, so framing it can only be
                   someone else's idea.
  no-referrer      an order number or a product path should not travel in a
                   `Referer` to whatever an error page happened to link to.
  HSTS             sent only when deployed, because a browser that sees it once
                   refuses plain http to that host for a year - a promise worth
                   keeping in production and a nuisance on localhost.
"""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

#: One year, and including subdomains. Preloading is deliberately not requested:
#: the preload list is effectively permanent and belongs to a decision about the
#: whole domain, not to this service.
HSTS_VALUE = "max-age=31536000; includeSubDomains"

#: `default-src 'none'` says the response may load nothing at all, which is
#: exactly right for JSON and makes an accidental HTML body inert.
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"

BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": API_CSP,
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds the headers without overwriting one a handler set on purpose."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)

        for name, value in BASE_HEADERS.items():
            response.headers.setdefault(name, value)

        if settings.is_deployed:
            response.headers.setdefault("Strict-Transport-Security", HSTS_VALUE)

        return response
