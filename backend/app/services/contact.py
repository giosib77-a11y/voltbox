"""Normalising the contact details an order is looked up by.

What it does: turns an email or a phone number into one canonical form, so that
two spellings of the same contact compare equal.
Where it fits: `services/order.py` uses it to decide whether a repeated
Idempotency-Key belongs to the same person, and `get_by_number` uses it to
decide whether a guest may read an order. Both answers have to agree - an order
a guest can read must be one they could have replayed, and the other way round.

Notes: normalisation happens at comparison time, on both sides, so the values
already stored keep working without a data migration. Nothing here is written
back to the database.
"""

from __future__ import annotations

import re

#: Georgia. Numbers are stored locally ("555123456") and typed in every shape.
COUNTRY_CODE = "995"

#: Georgian mobile numbers are nine digits, starting with 5.
LOCAL_LENGTH = 9

_NON_DIGITS = re.compile(r"\D")


def normalize_email(value: str | None) -> str | None:
    """Trimmed and lowercased, or None when there is nothing to compare."""
    if not value:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def normalize_phone(value: str | None) -> str | None:
    """A phone number in E.164, as far as the input allows.

    "555 12 34 56", "555123456" and "+995 555 123 456" are one person, and a
    guest who typed the spaces at checkout must still be able to find the
    order afterwards.

    An input that is already international (a leading `+`, or a Georgian
    country code) is kept as it is; a bare nine-digit local number gets the
    country code. Anything else is returned as digits behind a `+` rather than
    guessed at - a wrong guess would silently stop matching.
    """
    if not value:
        return None

    raw = value.strip()
    digits = _NON_DIGITS.sub("", raw)
    if not digits:
        return None

    if raw.startswith("+"):
        return f"+{digits}"

    # A trunk zero in front of a local number: 0555123456 -> 555123456
    if len(digits) == LOCAL_LENGTH + 1 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) == LOCAL_LENGTH:
        return f"+{COUNTRY_CODE}{digits}"

    return f"+{digits}"


def normalize_contact(value: str | None) -> str | None:
    """Normalise a value that may be either an email or a phone number.

    The guest lookup takes one field, because asking a shopper which of the two
    they used is a worse experience than working it out here.
    """
    if not value:
        return None
    return normalize_email(value) if "@" in value else normalize_phone(value)


def contact_matches(candidate: str | None, *, email: str | None, phone: str | None) -> bool:
    """True when `candidate` is the same contact as either stored value.

    Both sides are normalised here, which is what lets orders written before
    this module existed keep matching.
    """
    wanted = normalize_contact(candidate)
    if wanted is None:
        return False
    return wanted in {
        value for value in (normalize_email(email), normalize_phone(phone)) if value is not None
    }
