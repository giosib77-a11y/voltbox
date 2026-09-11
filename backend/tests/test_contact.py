"""Contact normalisation.

What it covers: two spellings of one contact have to compare equal, because the
same helper decides whether a repeated Idempotency-Key belongs to the caller
and whether a guest may read an order. If those two answers ever disagree, one
of them is a hole.

Normalisation happens at comparison time on both sides, so the rows written
before this module existed - bare local numbers like "555123456" - still match
what a shopper types later.
"""

import pytest
from app.services.contact import (
    contact_matches,
    normalize_contact,
    normalize_email,
    normalize_phone,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("giorgi@example.ge", "giorgi@example.ge"),
        ("  Giorgi@Example.GE  ", "giorgi@example.ge"),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_email(raw: str | None, expected: str | None) -> None:
    assert normalize_email(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # The shape the database already holds.
        ("555123456", "+995555123456"),
        ("555 12 34 56", "+995555123456"),
        ("(555) 12-34-56", "+995555123456"),
        ("+995 555 123 456", "+995555123456"),
        ("995555123456", "+995555123456"),
        # A trunk zero in front of a local number.
        ("0555123456", "+995555123456"),
        # Not Georgian: kept as given rather than guessed at, because a wrong
        # guess would silently stop matching.
        ("+44 20 7123 4567", "+442071234567"),
        ("", None),
        ("---", None),
        (None, None),
    ],
)
def test_phone(raw: str | None, expected: str | None) -> None:
    assert normalize_phone(raw) == expected


def test_an_email_and_a_phone_are_told_apart_by_the_at_sign() -> None:
    assert normalize_contact("Giorgi@Example.GE") == "giorgi@example.ge"
    assert normalize_contact("555 12 34 56") == "+995555123456"


def test_a_stored_order_matches_either_contact_it_was_placed_with() -> None:
    stored = {"email": "Giorgi@Example.GE", "phone": "555123456"}

    assert contact_matches("giorgi@example.ge", **stored)
    assert contact_matches("+995 555 12 34 56", **stored)


@pytest.mark.parametrize("candidate", [None, "", "nino@example.ge", "599999999"])
def test_anything_else_does_not_match(candidate: str | None) -> None:
    """Including nothing at all: an absent contact must never match an order."""
    assert not contact_matches(candidate, email="giorgi@example.ge", phone="555123456")


def test_a_guest_order_without_an_email_cannot_be_matched_by_one() -> None:
    """None on the stored side must not become a wildcard."""
    assert not contact_matches(None, email=None, phone="555123456")
    assert contact_matches("555123456", email=None, phone="555123456")
