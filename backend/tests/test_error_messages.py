"""Every error code the API can send has Georgian words on the other side.

The contract is that `code` is stable and `message` is written for whoever is
reading a log. That makes the code the thing the UI translates - and a new one
added here with no entry over there reaches a Georgian-speaking shopper as
English server text, which is how "Internal server error" and "Invalid request"
came to be shown to customers.

Where the words live: `apiErrors.<CODE>` in frontend/src/i18n/ka.json (and, for
the codes only the admin panel meets, frontend/src/admin/i18n/ka.json), which
httpClient.js looks up by code. An entry is either a sentence or, for a code
whose message depends on its details (how many are left, how long to wait),
an object of sentences that one of httpClient's DETAILED_MESSAGES functions
chooses between. An object with no function would reach the screen as
i18next's "returned an object instead of string", so that counts as missing.

The admin file is loaded only with the admin chunk, so a code a customer can
meet must not be in it: the customer would see the server's English text. The
last test therefore requires every code in the admin file to be raised only
from admin-only modules (or from the listed exceptions).

This test reads the frontend's files rather than importing them: one assertion
against the real source is worth more than a duplicated list that would drift
the same way. The guards below fail by name if either file or the shape of
either moves - the map used to live in httpClient.js itself, and when it moved
nothing here noticed until every code reported itself untranslated.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND_SRC = BACKEND.parent / "frontend" / "src"
CLIENT = FRONTEND_SRC / "services" / "httpClient.js"
GEORGIAN = FRONTEND_SRC / "i18n" / "ka.json"
# The codes only the admin panel can meet; its chunk registers them on top of
# ka.json (admin/adminTexts.js), so together the two files are the whole map.
ADMIN_GEORGIAN = FRONTEND_SRC / "admin" / "i18n" / "ka.json"

GEORGIAN_LETTER = re.compile(r"[ა-ჿ]")


def _where_the_backend_raises() -> dict[str, set[str]]:
    """code -> the files under app/ (posix paths relative to it) that name it."""
    where: dict[str, set[str]] = {}
    for path in (BACKEND / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        found = set(re.findall(r'code=["\']([A-Z_]+)["\']', text))
        found |= set(re.findall(r'code: str = ["\']([A-Z_]+)["\']', text))
        # The status -> code map in core/errors.py.
        found |= set(re.findall(r'\d{3}:\s*"([A-Z_]+)"', text))
        for code in found:
            where.setdefault(code, set()).add(path.relative_to(BACKEND / "app").as_posix())
    return where


def _codes_the_backend_can_send() -> set[str]:
    return set(_where_the_backend_raises())


def _georgian_entries() -> dict[str, Any]:
    """`apiErrors` from ka.json and the admin's ka.json: code -> sentence, or
    code -> {variant: sentence}."""
    merged: dict[str, Any] = {}
    for path in (GEORGIAN, ADMIN_GEORGIAN):
        assert path.exists(), path
        entries = json.loads(path.read_text(encoding="utf-8")).get("apiErrors")
        assert isinstance(entries, dict), f"{path} has no apiErrors section"
        merged |= entries
    return {key: value for key, value in merged.items() if re.fullmatch(r"[A-Z_]+", key)}


def _codes_with_a_detailed_message() -> set[str]:
    """The codes httpClient.js answers with a function of the details."""
    text = CLIENT.read_text(encoding="utf-8")
    assert "const DETAILED_MESSAGES = {" in text, f"DETAILED_MESSAGES moved out of {CLIENT.name}"
    block = text[text.index("const DETAILED_MESSAGES = {") :]
    block = block[: block.index("\n};")]
    return set(re.findall(r"^\s{2}([A-Z_]+):", block, re.M))


def _is_georgian(value: Any) -> bool:
    if isinstance(value, str):
        return bool(GEORGIAN_LETTER.search(value))
    if isinstance(value, dict):
        return bool(value) and all(_is_georgian(item) for item in value.values())
    return False


def _codes_the_frontend_translates() -> set[str]:
    detailed = _codes_with_a_detailed_message()
    return {
        code
        for code, value in _georgian_entries().items()
        if _is_georgian(value) and (isinstance(value, str) or code in detailed)
    }


def test_the_frontend_map_was_found_at_all() -> None:
    """Guards the test itself: a moved file or section would make everything
    below fail for the wrong reason, or pass."""
    assert CLIENT.exists(), CLIENT
    # The lookup that turns a code into ka.json's words. Without it the
    # entries below are never read, whatever they say.
    assert "`apiErrors.${code}`" in CLIENT.read_text(encoding="utf-8"), (
        f"{CLIENT.name} no longer looks codes up under apiErrors"
    )
    assert len(_georgian_entries()) > 20
    assert {"INSUFFICIENT_STOCK", "TOO_MANY_LOGIN_ATTEMPTS"} <= _codes_with_a_detailed_message()


def test_every_code_is_worth_something() -> None:
    """A sanity check on the extraction, not on the code."""
    codes = _codes_the_backend_can_send()

    assert "INSUFFICIENT_STOCK" in codes
    assert "INTERNAL_ERROR" in codes
    assert len(codes) > 40


@pytest.mark.parametrize("code", sorted(_codes_the_backend_can_send()))
def test_the_shopper_is_not_shown_english(code: str) -> None:
    translated = _codes_the_frontend_translates()

    assert code in translated, (
        f"{code} has no Georgian message under apiErrors in {GEORGIAN.name} "
        f"(or it has variants and no DETAILED_MESSAGES entry in {CLIENT.name}). "
        "The server's own text is written for a log, so without one it reaches "
        "the screen in English."
    )


# Codes in the admin file that a shared module raises, though only on an admin
# path or as a programming error a customer cannot trigger. Each names the one
# file allowed, so a new raise anywhere else still fails the test below.
ADMIN_CODES_IN_SHARED_FILES = {
    # services/inventory.py: raised by `validate_manual_adjustment`, called only
    # by routes/admin/inventory.py, and by `adjust_stock`, whose other callers
    # (checkout, order status, product create) pass a non-zero change and a
    # constant system reason.
    "EMPTY_ADJUSTMENT": {"services/inventory.py"},
    "UNKNOWN_REASON": {"services/inventory.py"},
    "REASON_NOT_MANUAL": {"services/inventory.py"},
    "NOTE_REQUIRED": {"services/inventory.py"},
    # main.py's body limit: the image limit applies only to POST
    # /admin/products/*/images (`_body_limit_for`); storage.py raises the same code.
    "IMAGE_TOO_LARGE": {"main.py"},
}


def _is_admin_only_module(path: str) -> bool:
    return (
        path.startswith("api/v1/routes/admin/")
        or re.fullmatch(r"services/admin_[a-z_]+\.py", path) is not None
        or path in {"services/storage.py", "services/order_trash.py"}
    )


def test_a_code_in_the_admin_file_is_raised_only_by_admin_modules() -> None:
    """The admin file is not loaded on the storefront. A code a customer can meet
    that sits only there is shown to a Georgian shopper as the server's English."""
    assert ADMIN_GEORGIAN.exists(), ADMIN_GEORGIAN
    admin_entries = json.loads(ADMIN_GEORGIAN.read_text(encoding="utf-8")).get("apiErrors")
    assert isinstance(admin_entries, dict), f"{ADMIN_GEORGIAN} has no apiErrors section"
    admin_codes = {key for key in admin_entries if re.fullmatch(r"[A-Z_]+", key)}
    assert len(admin_codes) > 20

    where = _where_the_backend_raises()
    # An exception for a code that is no longer in the admin file is stale.
    assert set(ADMIN_CODES_IN_SHARED_FILES) <= admin_codes
    # A path that no longer exists would pass this test for the wrong reason.
    assert _is_admin_only_module("services/admin_product.py")
    assert not _is_admin_only_module("services/order.py")
    assert (BACKEND / "app" / "api" / "v1" / "routes" / "admin").is_dir()

    shared = {
        code: sorted(
            path
            for path in where.get(code, set())
            if not _is_admin_only_module(path)
            and path not in ADMIN_CODES_IN_SHARED_FILES.get(code, set())
        )
        for code in sorted(admin_codes)
    }
    shared = {code: paths for code, paths in shared.items() if paths}

    assert not shared, (
        f"in admin/i18n/ka.json but raised outside the admin modules: {shared}. "
        "A customer can meet these, and i18n/ka.json is where they belong "
        "(or add a commented exception to ADMIN_CODES_IN_SHARED_FILES)."
    )
