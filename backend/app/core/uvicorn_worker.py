"""The gunicorn worker class production runs: UvicornWorker without the Server header.

What it does: uvicorn adds `Server: uvicorn` to every response unless told not
to (`server_header=False` in its Config). Naming the server software hands a
scanner a free fingerprint and tells it which advisories to try.

Why a subclass and not a flag: gunicorn builds uvicorn's Config inside
`UvicornWorker.__init__` from `CONFIG_KWARGS`, and that class attribute is the
one supported place to add to it. `--no-server-header` is a flag of the
`uvicorn` command and gunicorn never sees it.

Why it lives in `app/`: the Dockerfile copies `app` into the image, so the
module is there without a new COPY line, and gunicorn.conf.py names it by
import path (`worker_class`).

What still holds: only this one header is dropped; loop, http and everything
else come from `UvicornWorker.CONFIG_KWARGS` unchanged. Nothing in the
application imports this module - it needs gunicorn, which is installed on the
Linux image only - so the tests that must run everywhere read the class from its
source, and only the one that needs gunicorn imports it (tests/test_rate_limit.py).
"""

from uvicorn.workers import UvicornWorker


class NoServerHeaderWorker(UvicornWorker):
    # Not a ClassVar: uvicorn declares it as a plain annotated attribute, and a
    # ClassVar here would be an incompatible override for mypy. Never mutated.
    CONFIG_KWARGS = {**UvicornWorker.CONFIG_KWARGS, "server_header": False}  # noqa: RUF012
