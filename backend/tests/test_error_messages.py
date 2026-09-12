"""Every error code the API can send has Georgian words on the other side.

The contract is that `code` is stable and `message` is written for whoever is
reading a log. That makes the code the thing the UI translates - and a new one
added here with no entry over there reaches a Georgian-speaking shopper as
English server text, which is how "Internal server error" and "Invalid request"
came to be shown to customers.

This test reads the frontend's map as a file rather than importing it: one
assertion against the real source is worth more than a duplicated list that
would drift the same way.
"""

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
CLIENT = BACKEND.parent / "frontend" / "src" / "services" / "httpClient.js"


def _codes_the_backend_can_send() -> set[str]:
    codes: set[str] = set()
    for path in (BACKEND / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        codes |= set(re.findall(r'code=["\']([A-Z_]+)["\']', text))
        codes |= set(re.findall(r'code: str = ["\']([A-Z_]+)["\']', text))
        # The status -> code map in core/errors.py.
        codes |= set(re.findall(r'\d{3}:\s*"([A-Z_]+)"', text))
    return codes


def _codes_the_frontend_translates() -> set[str]:
    text = CLIENT.read_text(encoding="utf-8")
    block = text[text.index("const CODE_MESSAGES") : text.index("Pulls message / code")]
    return set(re.findall(r"^\s{2}([A-Z_]+):", block, re.M))


def test_the_frontend_map_was_found_at_all() -> None:
    """Guards the test itself: a moved file would make everything below pass."""
    assert CLIENT.exists(), CLIENT
    assert len(_codes_the_frontend_translates()) > 20


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
        f"{code} has no Georgian message in {CLIENT.name}. "
        "The server's own text is written for a log, so without an entry there "
        "it reaches the screen in English."
    )
