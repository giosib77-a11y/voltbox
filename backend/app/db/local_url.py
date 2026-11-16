"""Whether a database URL points at this machine - for the guards that must never
reach the live database.

Why this exists (2026-11-12): a pytest plugin imported `app.core.config` before
tests/conftest.py had set its environment, `Settings` read `backend/.env`, and the
suite's session fixture ran `alembic downgrade base` against live Supabase. The
environment switches alone cannot stop that, so tests/conftest.py and
alembic/env.py each check the URL they are about to connect to, using this.

Pure on purpose: no settings, no I/O, so both callers can import it first and a
test can feed it any URL. Messages carry the host and the database name only -
never the password or the whole URL.

The same answer also decides TLS: `Settings.requires_ssl` (app/core/config.py)
is `not is_local_database_url(DATABASE_URL)`, and `build_connect_args` sends no
TLS to the database when it is False. So `LOCAL_HOSTS` is not only the guards'
list - a host added to it for their convenience (`db`, `host.docker.internal`)
also connects to Postgres in plaintext, in every environment.
"""

from collections.abc import Mapping

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

#: Extending this also turns TLS to the database off for the new host
#: (`Settings.requires_ssl` reads it through `is_local_database_url`): only add
#: a host that really is this machine.
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

#: libpq and asyncpg accept these in the query string and let them win over the
#: host written in the URL, so a "localhost" URL could still connect elsewhere.
_HOST_OVERRIDES = ("host", "hostaddr")

ALLOW_REMOTE_MIGRATION = "VOLTBOX_ALLOW_REMOTE_MIGRATION"


def _parse(url: str | URL) -> URL | None:
    try:
        return make_url(url)
    except (ArgumentError, ValueError):
        return None


def is_local_database_url(url: str | URL) -> bool:
    """True only when the connection can go nowhere but this machine.

    A missing host is not local: asyncpg then falls back to PGHOST or a unix
    socket, which this check cannot see. Anything unparseable is not local.
    """
    parsed = _parse(url)
    if parsed is None or not parsed.host:
        return False
    if any(key in parsed.query for key in _HOST_OVERRIDES):
        return False
    return parsed.host.lower() in LOCAL_HOSTS


def describe_database_url(url: str | URL) -> str:
    """`host=..., database=...` for an error message; no credentials, no query values."""
    parsed = _parse(url)
    if parsed is None:
        return "an unparseable database URL"
    text = f"host={parsed.host or '(none)'}, database={parsed.database or '(none)'}"
    if any(key in parsed.query for key in _HOST_OVERRIDES):
        text += " (the query string overrides the host)"
    return text


def migration_refusal(url: str | URL, environ: Mapping[str, str]) -> str | None:
    """Why `alembic` may not run online against `url`, or None when it may.

    A non-local host is refused unless VOLTBOX_ALLOW_REMOTE_MIGRATION=1. Only
    online mode asks: `--sql` never connects and stays unrestricted. The name of
    the database is not checked - the dev (`voltbox`) and e2e (`voltbox_e2e`)
    databases on localhost must still migrate.
    """
    if is_local_database_url(url) or environ.get(ALLOW_REMOTE_MIGRATION) == "1":
        return None
    return (
        f"Refusing to run alembic online against {describe_database_url(url)}: it is not "
        "a local database. Migrations on live Supabase go through "
        "`alembic upgrade <from>:<to> --sql` and the SQL Editor (docs/deployment.md, "
        f"section 5). To migrate a non-local database deliberately, set {ALLOW_REMOTE_MIGRATION}=1."
    )
