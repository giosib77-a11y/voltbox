"""The test suite must never load `backend/.env`.

That file points at the live Supabase project. `Settings` opens `.env` from the
working directory, and pytest runs from `backend/`, so without the switch every
run would put the live URL and keys in the process.
"""

from pathlib import Path

import pytest
from app.core.config import Settings


def test_the_suite_has_the_dotenv_switch_on() -> None:
    assert Settings.model_config["env_file"] is None


def test_a_dotenv_in_the_working_directory_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("APP_NAME=read-from-the-dotenv-file\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert Settings().app_name != "read-from-the-dotenv-file"
