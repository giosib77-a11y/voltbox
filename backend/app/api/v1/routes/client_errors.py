"""Where a crash in somebody's browser goes.

What it does: accepts one report from the storefront's ErrorBoundary and writes
it to the same log stream as everything else.
Where it fits: called only by components/common/ErrorBoundary.jsx.

Why it exists: a server error has been visible since section 13 - a traceback,
a request id, a line in the access log. A crash in a customer's browser had
none of that. The screen went blank in Tbilisi and nothing anywhere recorded
it; the shop found out when somebody phoned, or never.

This is not a monitoring service and does not pretend to be one. It is the
smallest thing that makes those crashes visible in a log the host already
collects, using nothing that is not already installed.

Notes: the body is attacker-controlled - anyone can POST here - so it is
rate limited, strictly shaped, and truncated before it reaches the log. The
endpoint answers 204 whatever happens: a reporting channel that returns errors
would have the ErrorBoundary reporting its own failure to report.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response, status

from app.core.rate_limit import CLIENT_ERROR_RATE_LIMIT, limiter
from app.schemas.client_error import ClientErrorReport

router = APIRouter(prefix="/client-errors", tags=["monitoring"])

logger = logging.getLogger("voltbox.client")


@router.post(
    "",
    summary="Report a crash in the browser",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
@limiter.limit(CLIENT_ERROR_RATE_LIMIT)
async def report(request: Request, payload: ClientErrorReport) -> Response:
    logger.error(
        "client error",
        extra={
            "extra_fields": {
                "request_id": getattr(request.state, "request_id", None),
                # Everything below was typed by a browser we do not control.
                "client_message": payload.message,
                "client_path": payload.path,
                "client_stack": payload.stack,
                "user_agent": request.headers.get("user-agent", "")[:200],
            }
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
