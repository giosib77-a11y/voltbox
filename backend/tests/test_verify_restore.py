"""scripts/verify_restore.py must never reach the live database.

It used to read backend/.env to learn the live URL. It now reads nothing and
accepts only a localhost `--against`, so a remote (live) source is refused by
its host alone.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.factories import load_script

LOCAL_RESTORED = "postgresql://voltbox:voltbox@localhost:55433/voltbox_restore"
LOCAL_SOURCE = "postgresql://voltbox:voltbox@localhost:55432/voltbox_dev"
REMOTE = "postgresql://u:p@db.abcdefgh.supabase.co:5432/postgres"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_restore.py"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@db.abcdefgh.supabase.co:5432/postgres",
        "postgresql://u:p@aws-0-eu.pooler.supabase.com:6543/postgres",
        "postgresql://u:p@localhost.evil.example:5432/db",
        "postgresql://u:p@example.com:5432/localhost",
        "postgresql://localhost:x@evil.example/db",
        "postgresql://u:p@10.0.0.5:5432/db",
        "postgresql://u:p@localhost:5432/db?host=db.x.supabase.co",
        "postgresql://u:p@localhost:5432/db?hostaddr=10.0.0.5",
        "postgresql://u:p@localhost:5432/db?ssl=disable&host=db.x.supabase.co",
        "not a url",
        "",
    ],
)
def test_a_non_local_source_is_not_local(url: str) -> None:
    assert load_script("verify_restore").is_local(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://voltbox:voltbox@localhost:55432/voltbox_dev",
        "postgresql://voltbox:voltbox@127.0.0.1:55432/voltbox_dev",
        "postgresql://voltbox:voltbox@[::1]:55432/voltbox_dev",
    ],
)
def test_a_localhost_source_is_local(url: str) -> None:
    assert load_script("verify_restore").is_local(url) is True


def test_main_refuses_a_remote_source_before_connecting(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_script("verify_restore")

    async def must_not_connect(url: str) -> dict[str, list[str]]:
        raise AssertionError(f"connected to {url}")

    monkeypatch.setattr(module, "read", must_not_connect)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_restore.py",
            LOCAL_RESTORED,
            "--against",
            "postgresql://u:p@db.abcdefgh.supabase.co:5432/postgres",
        ],
    )

    assert asyncio.run(module.main()) == 2
    assert "refusing --against" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("restored", "against", "refused"),
    [
        (REMOTE, LOCAL_SOURCE, "restored"),
        ("postgresql://u:p@localhost:5432/db?host=db.x.supabase.co", LOCAL_SOURCE, "restored"),
        (LOCAL_RESTORED, "postgresql://u:p@localhost:5432/db?host=db.x.supabase.co", "--against"),
    ],
)
def test_main_refuses_a_remote_url_in_either_position(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    restored: str,
    against: str,
    refused: str,
) -> None:
    module = load_script("verify_restore")

    async def must_not_connect(url: str) -> dict[str, list[str]]:
        raise AssertionError(f"connected to {url}")

    monkeypatch.setattr(module, "read", must_not_connect)
    monkeypatch.setattr(sys, "argv", ["verify_restore.py", restored, "--against", against])

    assert asyncio.run(module.main()) == 2
    assert f"refusing {refused}:" in capsys.readouterr().out


def test_main_has_no_default_source(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_script("verify_restore")
    monkeypatch.setattr(sys, "argv", ["verify_restore.py", LOCAL_RESTORED])

    with pytest.raises(SystemExit) as exit_info:
        asyncio.run(module.main())

    assert exit_info.value.code == 2


def test_the_module_does_not_read_a_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = "postgresql://sentinel:sentinel@sentinel.invalid:5432/sentinel"
    (tmp_path / ".env").write_text(f"DATABASE_URL={sentinel}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    module = load_script("verify_restore")

    assert not hasattr(module, "dotenv_values")
    assert sentinel not in {v for v in vars(module).values() if isinstance(v, str)}


@pytest.mark.parametrize(
    "args",
    [
        [REMOTE, "--against", LOCAL_SOURCE],
        [LOCAL_RESTORED, "--against", "postgresql://u:p@localhost:5432/db?host=db.x.supabase.co"],
    ],
)
def test_the_script_runs_to_its_url_check_without_loading_a_dotenv(
    tmp_path: Path, args: list[str]
) -> None:
    # pytest has already imported app.core.config with the dotenv switched off, so
    # only a fresh interpreter can show what the script itself pulls in. `-I`
    # keeps the cwd and PYTHON* variables out of sys.path; the sentinel .env sits
    # in the cwd, where Settings would look for it, and JWT_SECRET is unset, so
    # an import of app settings either loads the sentinel or dies on JWT_SECRET.
    sentinel = "postgresql://sentinel:sentinel@sentinel.invalid:5432/sentinel"
    (tmp_path / ".env").write_text(f"DATABASE_URL={sentinel}\n", encoding="utf-8")
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"VOLTBOX_NO_DOTENV", "JWT_SECRET", "DATABASE_URL"}
    }

    done = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-I", str(SCRIPT), *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert done.returncode == 2, done.stderr
    assert "refusing" in done.stdout
    assert "sentinel" not in done.stdout + done.stderr
    assert "JWT_SECRET" not in done.stderr.upper()
