"""Child process for test_conftest_guard.py - not a test, not a conftest, not a plugin.

It reproduces the 2026-11-12 incident (A-061) with plain imports and nothing
else. It never opens a connection: importing `app.db.session` only builds an
engine, and the parent gives it an unresolvable host besides.

  settings-first   import `app.core.config`, then `tests.conftest`
  conftest-only    import `tests.conftest`

Exit 0 and a line "imported" mean the conftest guards let the import through.
"""

import importlib
import sys


def main(mode: str) -> None:
    if mode == "settings-first":
        importlib.import_module("app.core.config")
    elif mode != "conftest-only":
        raise SystemExit(f"unknown mode: {mode}")
    importlib.import_module("tests.conftest")
    print("imported")


if __name__ == "__main__":
    main(sys.argv[1])
