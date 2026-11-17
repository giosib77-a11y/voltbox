"""tests/conftest.py refuses at import, not only when its helpers are called.

A-064: test_database_guard.py calls `require_settings_built_for_this_run()` and
`require_test_database()` directly, so deleting the two calls at module level in
conftest.py left it green - and those calls are what stops a run before pytest
collects anything. Here a child process imports `app.core.config` and then
`tests.conftest` (the A-061 order, with no plugin) and the import must fail.

The child never reaches a database: its URLs are `db.invalid.example` (RFC 2606,
never resolves) or local, it opens no connection, `.env` is switched off and its
working directory is empty. Its environment is built from scratch, so no real
credential of this process can reach it.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
CHILD = Path(__file__).with_name("_guard_child.py")
REMOTE = "postgresql+asyncpg://u:hunter2-password@db.invalid.example/voltbox"
LOCAL_TEST = "postgresql://voltbox:voltbox@localhost:55432/voltbox_test"
# What Windows needs to start a Python process at all; nothing here is a secret.
SYSTEM_VARIABLES = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "COMSPEC")


def _import_in_child(
    mode: str, tmp_path: Path, *, database_url: str, test_database_url: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = {name: os.environ[name] for name in SYSTEM_VARIABLES if name in os.environ}
    env.update(
        {
            "PYTHONPATH": str(BACKEND_DIR),
            "VOLTBOX_NO_DOTENV": "1",
            "APP_ENV": "test",
            "JWT_SECRET": "test-only-secret-value-that-is-long-enough-32",
            "DATABASE_URL": database_url,
        }
    )
    if test_database_url is not None:
        env["TEST_DATABASE_URL"] = test_database_url
    return subprocess.run(  # noqa: S603 - our own interpreter and script, fixed arguments
        [sys.executable, str(CHILD), mode],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,  # a cold `import app` takes 8-14 s on a Windows dev machine
        check=False,
    )


def test_conftest_imported_after_the_settings_aborts_the_run(tmp_path: Path) -> None:
    result = _import_in_child("settings-first", tmp_path, database_url=REMOTE)

    assert result.returncode != 0
    assert "UnsafeTestDatabaseError" in result.stderr
    assert "built before tests/conftest.py" in result.stderr
    assert "db.invalid.example" in result.stderr
    assert "imported" not in result.stdout
    assert "hunter2-password" not in result.stdout + result.stderr


# One refusal is enough to show the module-level call is there: removing it lets
# every bad URL through alike. Each refusal's wording (not local, not `_test`)
# is checked by calling the guard directly in test_database_guard.py, without a
# child's 8-14 s cold import of `app`.
@pytest.mark.parametrize(
    ("url", "expected"),
    [(REMOTE, "not a local database")],
    ids=["remote-host"],
)
def test_conftest_aborts_the_run_when_the_engine_is_not_a_local_test_database(
    tmp_path: Path, url: str, expected: str
) -> None:
    result = _import_in_child(
        "conftest-only", tmp_path, database_url=LOCAL_TEST, test_database_url=url
    )

    assert result.returncode != 0
    assert "UnsafeTestDatabaseError" in result.stderr
    assert "as the test engine" in result.stderr
    assert expected in result.stderr
    assert "imported" not in result.stdout
    assert "hunter2-password" not in result.stdout + result.stderr


def test_conftest_imports_cleanly_for_a_local_test_database(tmp_path: Path) -> None:
    # The control: the refusals above come from the guards, not from the child
    # failing to start (a missing path, a missing variable). "settings-first"
    # imports conftest too; each child costs seconds, so only one runs.
    result = _import_in_child(
        "settings-first", tmp_path, database_url=LOCAL_TEST, test_database_url=LOCAL_TEST
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "imported"
