"""The Host check, and a log line naming TRUSTED_HOSTS when it refuses a request.

Starlette's TrustedHostMiddleware answers a Host it does not know with
`400 Invalid host header` and writes nothing. It sits outside the middleware
that writes the access log, so a refused request left no line at all. The
mistake that refuses every request - TRUSTED_HOSTS listing the storefront's
domain and not the API's own - took down the health check with nothing in the
log pointing at the setting.

The line names the setting and not the Host that was sent. A refused Host is by
definition one this server did not expect, so its sender is a stranger as often
as the operator, and it would be the one field in the log a stranger chooses.
The operator can act without it: the names to add are the ones the API is
served on, which the hosting dashboard shows.
"""

import logging
from collections.abc import Sequence

from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("voltbox.hosts")

REFUSED = (
    "A request's Host is not in TRUSTED_HOSTS, so it was not served. If every "
    "request is refused, the health check included, TRUSTED_HOSTS is missing the "
    "name this API is served on."
)

#: Set on the scope by the app Starlette hands an accepted request to. Starlette
#: builds its refusal inline with no hook, so the mark missing afterwards is how
#: a refusal is told from a request the application itself answered with a 400.
_ADMITTED = "voltbox.host_admitted"


class LoggedTrustedHostMiddleware(TrustedHostMiddleware):
    """Starlette's check, unchanged, plus one line for each request it refuses."""

    def __init__(self, app: ASGIApp, allowed_hosts: Sequence[str]) -> None:
        super().__init__(self._admit, allowed_hosts=allowed_hosts)
        self._next = app

    async def _admit(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope[_ADMITTED] = True
        await self._next(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await super().__call__(scope, receive, send)
        if scope["type"] in ("http", "websocket") and not scope.get(_ADMITTED):
            logger.warning(REFUSED)
