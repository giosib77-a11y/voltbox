"""The suite and `alembic` refuse a database that is not on this machine.

2026-11-12 (A-061): a pytest plugin imported `app` before tests/conftest.py set
its environment, `Settings` read backend/.env, and the session fixture ran
`alembic downgrade base` against live Supabase. These tests pin the checks that
now stand between a wrong URL and a connection. Every URL here is local or
`db.invalid.example` (RFC 2606: it never resolves), so a guard that failed would
end in a DNS error, not in a real database.

The conftest helpers are reached as attributes of the module, so a missing one
fails its own test instead of the whole file at import.
"""

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.util import CommandError
from app.core.config import get_settings, settings
from app.db.local_url import (
    ALLOW_REMOTE_MIGRATION,
    describe_database_url,
    is_local_database_url,
    migration_refusal,
)
from app.db.session import engine
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from tests import conftest as suite

BACKEND_DIR = Path(__file__).resolve().parents[1]
REMOTE = "postgresql+asyncpg://u:hunter2-password@db.invalid.example/voltbox"


# --- which URLs count as local ----------------------------------------------


def test_bracketed_ipv6_loopback_parses_to_the_bare_address() -> None:
    assert make_url("postgresql://u:p@[::1]:55432/voltbox_test").host == "::1"


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_a_local_host_with_a_test_database_is_allowed(host: str) -> None:
    url = f"postgresql://u:p@{host}:55432/voltbox_test"

    assert is_local_database_url(url)
    suite.require_test_database(url, "a test")  # does not raise


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@db.invalid.example/voltbox_test",
        "postgresql://u:p@db.invalid.example:5432/voltbox_test?sslmode=require",
        "postgresql://u:p@/voltbox_test",
        "postgresql://u:p@localhost/voltbox_test?host=db.invalid.example",
        "postgresql://u:p@localhost/voltbox_test?hostaddr=10.0.0.1",
        "postgresql://u:p@localhost,db.invalid.example/voltbox_test",
        "not a url",
    ],
    ids=[
        "remote",
        "remote-with-sslmode",
        "no-host",
        "query-host",
        "query-hostaddr",
        "two-hosts",
        "garbage",
    ],
)
def test_anything_that_may_connect_elsewhere_is_not_local(url: str) -> None:
    assert not is_local_database_url(url)
    with pytest.raises(suite.UnsafeTestDatabaseError, match="not a local database"):
        suite.require_test_database(url, "a test")


@pytest.mark.parametrize("name", ["voltbox", "voltbox_e2e", "voltbox_test_old", ""])
def test_a_local_database_not_named_test_is_refused_by_the_suite(name: str) -> None:
    with pytest.raises(suite.UnsafeTestDatabaseError, match="must end in `_test`"):
        suite.require_test_database(f"postgresql://u:p@localhost:55432/{name}", "a test")


def test_the_refusal_names_host_and_database_but_not_the_password() -> None:
    with pytest.raises(suite.UnsafeTestDatabaseError) as raised:
        suite.require_test_database(REMOTE, "a test")

    message = str(raised.value)
    assert "db.invalid.example" in message
    assert "voltbox" in message
    assert "hunter2-password" not in message


def test_describe_never_prints_credentials_or_query_values() -> None:
    text = describe_database_url(
        "postgresql://u:hunter2-password@localhost/voltbox?host=secret-host"
    )

    assert text.startswith("host=localhost, database=voltbox")
    assert "hunter2-password" not in text
    assert "secret-host" not in text


# --- what the suite is about to connect to -----------------------------------


@pytest.mark.parametrize("direction", ["up", "down"])
@pytest.mark.parametrize(
    "url",
    [REMOTE, "postgresql+asyncpg://u:p@localhost:55432/voltbox"],
    ids=["remote-host", "local-dev-database"],
)
def test_run_alembic_refuses_before_alembic_is_called(
    monkeypatch: pytest.MonkeyPatch, direction: str, url: str
) -> None:
    calls: list[str] = []

    def spy(*args: object, **kwargs: object) -> None:
        calls.append("called")

    monkeypatch.setattr(command, "upgrade", spy)
    monkeypatch.setattr(command, "downgrade", spy)
    monkeypatch.setattr(settings, "database_url", SecretStr(url))

    # RuntimeError, not the helper's own class: on code without the guard the
    # failure must be "DID NOT RAISE" with the spy called, not an AttributeError.
    with pytest.raises(RuntimeError, match="the alembic target"):
        suite._run_alembic(direction)

    assert calls == []


def test_run_alembic_still_calls_alembic_for_the_test_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(command, "upgrade", lambda *a, **k: calls.append("up"))
    monkeypatch.setattr(command, "downgrade", lambda *a, **k: calls.append("down"))

    suite._run_alembic("up")
    suite._run_alembic("down")

    assert calls == ["up", "down"]


def test_the_engine_is_on_a_local_test_database() -> None:
    suite.require_test_database(engine.url, "the test engine")


# --- settings built before conftest ------------------------------------------


def test_settings_built_for_this_run_pass_the_check() -> None:
    suite.require_settings_built_for_this_run()


def _differing_in_one_field(
    *,
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    username: str | None = None,
) -> str:
    """The active test URL with the one field that is given altered.

    A-115: these URLs used to be literals, and the literal `localhost:5432/voltbox_test`
    IS the test database in CI (`TEST_DATABASE_URL` there is that URL), so the guard
    rightly accepted it and the test failed. Computed from the URL the run uses,
    each one differs from it in one compared field whatever `TEST_DATABASE_URL` is.
    tests/conftest.py has set `DATABASE_URL` before this module is collected.
    """
    active = make_url(os.environ["DATABASE_URL"])
    url = active.set(
        drivername="postgresql+asyncpg",
        host=host or active.host,
        port=port or active.port,
        database=database or active.database,
        username=username or active.username,
    )
    return url.render_as_string(hide_password=False)


_ACTIVE = make_url(os.environ["DATABASE_URL"])
_OTHER_HOST = "127.0.0.1" if _ACTIVE.host == "localhost" else "localhost"


@pytest.mark.parametrize(
    "url",
    [
        REMOTE,
        _differing_in_one_field(database=f"{_ACTIVE.database}_other"),
        _differing_in_one_field(port=(_ACTIVE.port or 5432) + 1),
        _differing_in_one_field(username=f"{_ACTIVE.username}_other"),
        _differing_in_one_field(host=_OTHER_HOST),
        "not a url",
    ],
    ids=["remote", "other-database", "other-port", "other-user", "other-host", "garbage"],
)
def test_settings_built_from_another_url_abort_the_run(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setattr(get_settings(), "database_url", SecretStr(url))

    with pytest.raises(suite.UnsafeTestDatabaseError, match=r"built before tests/conftest\.py"):
        suite.require_settings_built_for_this_run()


def test_settings_that_differ_only_in_scheme_and_sslmode_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Settings.normalize_database_url rewrites exactly these two things.
    expected = make_url(os.environ["DATABASE_URL"])
    same = expected.set(drivername="postgresql+asyncpg", query={"sslmode": "require"})
    monkeypatch.setattr(
        settings, "database_url", SecretStr(same.render_as_string(hide_password=False))
    )

    suite.require_settings_built_for_this_run()


# --- alembic/env.py -----------------------------------------------------------

LOCAL_DEV = "postgresql+asyncpg://voltbox:voltbox@localhost:55432/voltbox"
LOCAL_E2E = "postgresql+asyncpg://voltbox:voltbox@127.0.0.1:55432/voltbox_e2e"


@pytest.mark.parametrize("url", [LOCAL_DEV, LOCAL_E2E, "postgresql://u:p@[::1]/voltbox_test"])
def test_migrations_on_a_local_database_are_not_refused(url: str) -> None:
    assert migration_refusal(url, {}) is None


@pytest.mark.parametrize(
    "url",
    [
        REMOTE,
        "postgresql://u:p@/voltbox",
        "postgresql://u:p@localhost/voltbox?host=db.invalid.example",
    ],
    ids=["remote", "no-host", "query-host"],
)
def test_migrations_on_a_non_local_database_are_refused_unless_allowed(url: str) -> None:
    refusal = migration_refusal(url, {})

    assert refusal is not None
    assert ALLOW_REMOTE_MIGRATION in refusal
    assert "--sql" in refusal
    assert "hunter2-password" not in refusal
    assert migration_refusal(url, {ALLOW_REMOTE_MIGRATION: "1"}) is None
    # Only the exact value opts in.
    assert migration_refusal(url, {ALLOW_REMOTE_MIGRATION: "true"}) is not None
    assert migration_refusal(url, {ALLOW_REMOTE_MIGRATION: ""}) is not None


def _alembic(*args: str, url: str) -> subprocess.CompletedProcess[str]:
    """Run the alembic CLI in a child process whose database is `url` alone."""
    env = os.environ.copy()
    env.pop(ALLOW_REMOTE_MIGRATION, None)
    env.update(
        {
            "VOLTBOX_NO_DOTENV": "1",
            "APP_ENV": "test",
            "DATABASE_URL": url,
            "JWT_SECRET": "test-only-secret-value-that-is-long-enough-32",
            **dict.fromkeys(
                ("TELEGRAM_BOT_TOKEN", "RESEND_API_KEY", "SUPABASE_SERVICE_ROLE_KEY", "REDIS_URL"),
                "",
            ),
        }
    )
    return subprocess.run(  # noqa: S603 - our own interpreter, fixed arguments
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_online_alembic_refuses_a_remote_host_and_says_why() -> None:
    result = _alembic(
        "upgrade", "head", url="postgresql://u:hunter2-password@db.invalid.example/voltbox"
    )

    assert result.returncode != 0
    assert ALLOW_REMOTE_MIGRATION in result.stderr
    assert "--sql" in result.stderr
    assert "hunter2-password" not in result.stdout + result.stderr


# --- a percent-encoded password (A-065) -----------------------------------------
# alembic stores the URL in a ConfigParser, where a bare `%` is an interpolation
# syntax error whose message quotes the whole value. The password is made up.

PERCENT_PASSWORD = "p%40ss-w0rd"
PERCENT_LOCAL = f"postgresql+asyncpg://voltbox:{PERCENT_PASSWORD}@localhost:55432/voltbox_test"
PERCENT_REMOTE = f"postgresql+asyncpg://u:{PERCENT_PASSWORD}@db.invalid.example/voltbox"


class _EngineReachedError(Exception):
    """Raised by the stand-in engine factory, so no connection is ever opened."""


def test_offline_alembic_accepts_a_percent_encoded_password() -> None:
    result = _alembic("upgrade", "head", "--sql", url=PERCENT_REMOTE)

    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE" in result.stdout
    assert PERCENT_PASSWORD not in result.stdout + result.stderr
    assert "interpolation" not in result.stderr


def test_online_alembic_refusal_with_a_percent_password_does_not_print_it() -> None:
    result = _alembic("upgrade", "head", url=PERCENT_REMOTE)

    assert result.returncode != 0
    assert ALLOW_REMOTE_MIGRATION in result.stderr
    assert "interpolation" not in result.stderr
    assert PERCENT_PASSWORD not in result.stdout + result.stderr
    assert "p%40ss" not in result.stdout + result.stderr


def _run_env_online(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> tuple[list[str], list[dict[str, str]]]:
    """Run alembic/env.py online in this process with `url`, up to the engine.

    Returns the URLs the guard was asked about and the config sections the engine
    factory received. The factory raises, so nothing connects.
    """
    import sqlalchemy.ext.asyncio as sa_asyncio
    from app.db import local_url

    guarded: list[str] = []
    sections: list[dict[str, str]] = []
    real_refusal = local_url.migration_refusal

    def spy_refusal(candidate: str, environ: Mapping[str, str]) -> str | None:
        guarded.append(candidate)
        return real_refusal(candidate, environ)

    def stand_in_engine(section: dict[str, str], **_: object) -> object:
        sections.append(dict(section))
        raise _EngineReachedError

    monkeypatch.delenv(ALLOW_REMOTE_MIGRATION, raising=False)
    monkeypatch.setattr(settings, "database_url", SecretStr(url))
    monkeypatch.setattr(local_url, "migration_refusal", spy_refusal)
    monkeypatch.setattr(sa_asyncio, "async_engine_from_config", stand_in_engine)

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    with pytest.raises(_EngineReachedError):
        command.upgrade(config, "head")
    return guarded, sections


def test_the_guard_and_the_engine_see_the_percent_password_unescaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guarded, sections = _run_env_online(monkeypatch, PERCENT_LOCAL)

    assert guarded == [PERCENT_LOCAL]
    assert [section["sqlalchemy.url"] for section in sections] == [PERCENT_LOCAL]
    assert "%%" not in guarded[0]


def test_the_guard_refuses_a_remote_host_that_has_a_percent_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlalchemy.ext.asyncio as sa_asyncio

    # env.py refuses before it builds the engine, so `_run_env_online`, which
    # expects the engine factory to be reached, does not apply: drive it directly.
    def never(*_: object, **__: object) -> object:
        raise AssertionError("the engine was built for a refused target")

    monkeypatch.delenv(ALLOW_REMOTE_MIGRATION, raising=False)
    monkeypatch.setattr(settings, "database_url", SecretStr(PERCENT_REMOTE))
    monkeypatch.setattr(sa_asyncio, "async_engine_from_config", never)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))

    with pytest.raises(CommandError) as excinfo:
        command.upgrade(config, "head")

    assert ALLOW_REMOTE_MIGRATION in str(excinfo.value)
    assert PERCENT_PASSWORD not in str(excinfo.value)


def test_offline_alembic_is_unchanged_for_a_remote_host() -> None:
    result = _alembic("upgrade", "head", "--sql", url="postgresql://u:p@db.invalid.example/voltbox")

    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE" in result.stdout
    assert ALLOW_REMOTE_MIGRATION not in result.stderr
