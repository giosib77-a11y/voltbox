"""Every error code the API can send has Georgian words on the other side.

The contract is that `code` is stable and `message` is written for whoever is
reading a log. That makes the code the thing the UI translates - and a new one
added here with no entry over there reaches a Georgian-speaking shopper as
English server text, which is how "Internal server error" and "Invalid request"
came to be shown to customers.

Where the words live: `apiErrors.<CODE>` in frontend/src/i18n/ka.json, which
httpClient.js looks up by code. An entry is either a sentence or, for a code
whose message depends on its details (how many are left, how long to wait),
an object of sentences that one of httpClient's DETAILED_MESSAGES functions
chooses between. An object with no function would reach the screen as
i18next's "returned an object instead of string", so that counts as missing.

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

GEORGIAN_LETTER = re.compile(r"[ა-ჿ]")


def _codes_the_backend_can_send() -> set[str]:
    codes: set[str] = set()
    for path in (BACKEND / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        codes |= set(re.findall(r'code=["\']([A-Z_]+)["\']', text))
        codes |= set(re.findall(r'code: str = ["\']([A-Z_]+)["\']', text))
        # The status -> code map in core/errors.py.
        codes |= set(re.findall(r'\d{3}:\s*"([A-Z_]+)"', text))
    return codes


def _georgian_entries() -> dict[str, Any]:
    """`apiErrors` from ka.json: code -> sentence, or code -> {variant: sentence}."""
    assert GEORGIAN.exists(), GEORGIAN
    entries = json.loads(GEORGIAN.read_text(encoding="utf-8")).get("apiErrors")
    assert isinstance(entries, dict), f"{GEORGIAN.name} has no apiErrors section"
    return {key: value for key, value in entries.items() if re.fullmatch(r"[A-Z_]+", key)}


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
