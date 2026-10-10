"""scripts/verify_restore.py must never reach the live database.

It used to read backend/.env to learn the live URL. It now reads nothing and
accepts only a localhost `--against`, so a remote (live) source is refused by
its host alone.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from tests.factories import load_script

LOCAL_RESTORED = "postgresql://voltbox:voltbox@localhost:55433/voltbox_restore"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@db.abcdefgh.supabase.co:5432/postgres",
        "postgresql://u:p@aws-0-eu.pooler.supabase.com:6543/postgres",
        "postgresql://u:p@localhost.evil.example:5432/db",
        "postgresql://u:p@example.com:5432/localhost",
        "postgresql://localhost:x@evil.example/db",
        "postgresql://u:p@10.0.0.5:5432/db",
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
