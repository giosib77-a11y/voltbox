"""The rule for a NEW password (A-037), and what it must never touch.

What it covers: the common-password list shipped as a data file (its size and
its hash, so an edit is visible), the repetition/sequence filter, the
administrator's twelve-character minimum on change-password and reset-password,
and - as important as any refusal - that a password chosen under the old, looser
rule still signs in, because the rule applies only where a password is set.
Notes: the administrator's minimum on `scripts/manage_admin.py` is tested in
test_manage_admin.py; the Telegram message on an administrator's lock in
test_admin_lock_notice.py.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest
from app.core import security
from app.core.security import (
    COMMON_PASSWORDS,
    MIN_ADMIN_PASSWORD_LENGTH,
    is_common_password,
    is_patterned_password,
    verify_password,
)
from app.db.models import ROLE_ADMIN, ROLE_CUSTOMER, User
from app.services import auth as auth_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import auth_header, make_user

#: SHA-256 of SecLists' 10k-most-common.txt at upstream commit 913b327, as
#: recorded in common_passwords.NOTICE.txt. Updating the list means updating
#: both, deliberately.
LIST_SHA256 = "68782d6a4a19a4768d5f15dd66bd534e7a33055cc755411e33f16d18c50fdcce"

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
CHANGE = "/api/v1/auth/change-password"
RESET = "/api/v1/auth/reset-password"

#: What the rule must refuse for anyone.
REFUSED = [
    "aaaaaaaa",
    "11111111",
    "12345678",
    "87654321",
    "abcdefgh",
    "hgfedcba",
    "qwertyui",
    "qwertyuiop",
    "asdfghjk",
    "12345678a",
    "aaaaaaaa1",
    # Case does not hide a pattern.
    "Aaaaaaaa",
    "AbCdEfGh",
    "QWERTYUI",
    # Decorated common words: the digits and symbols people add to satisfy a rule.
    "Password1!",
    "monkey2024!",
    "#Dragon99",
    "  summer  ",
    # A pattern with a little added is still little.
    "abcdefgh1357",
    "qwertyuiop12",
    "abababab",
]

#: Refused as well, and only for an administrator, on length or on pattern.
ADMIN_REFUSED = ["aaaaaaaaaaaa", "123456789012", "Password123!"]

#: What an ordinary person types, and must be let through.
ACCEPTED = [
    "Tbilisi-Vake-2026",
    "k7#Rm2!pQz",
    "correct horse battery",
    "mzeqalaqi-ghame-77",
    "Xv9$kLm2#qRz",
    "ქართული პაროლი 2026!",
    "supersecret1",
    "brand-new-pass-7",
    # Exactly the five different characters left that the rule asks for.
    "abcdexk9zq",
]


def _list_bytes() -> bytes:
    # CRLF is normalised: a checkout that converted the line endings is the
    # same list, and .gitattributes keeps it LF in the repository anyway.
    return security._COMMON_PASSWORDS_FILE.read_bytes().replace(b"\r\n", b"\n")


# ── the list ─────────────────────────────────────────────────────────────────


def test_the_list_is_the_one_that_was_vetted() -> None:
    """A changed byte fails here, so an edit to the data is a visible decision."""
    assert hashlib.sha256(_list_bytes()).hexdigest() == LIST_SHA256


def test_the_list_is_loaded_whole_and_lower_cased() -> None:
    assert len(_list_bytes().splitlines()) >= 10_000
    assert len(COMMON_PASSWORDS) >= 10_000
    assert all(entry == entry.lower() for entry in COMMON_PASSWORDS)
    assert {"password", "123456", "qwerty", "monkey"} <= COMMON_PASSWORDS


def test_the_shops_own_words_are_merged_in() -> None:
    assert security._SHOP_COMMON_PASSWORDS <= COMMON_PASSWORDS
    assert {"georgia1", "sakartvelo", "1qaz2wsx", "admin123"} <= COMMON_PASSWORDS


def test_the_notice_with_the_licence_ships_beside_the_list() -> None:
    notice = security._COMMON_PASSWORDS_FILE.with_name("common_passwords.NOTICE.txt")
    text = notice.read_text(encoding="utf-8")

    assert LIST_SHA256 in text
    assert "913b327317496d062bcc7cace524aaad8a693be2" in text
    assert "MIT License" in text
    assert "Copyright (c) 2018 Daniel Miessler" in text
    assert "THE SOFTWARE IS PROVIDED" in text


def test_a_missing_list_stops_the_import_instead_of_accepting_everything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(security, "_COMMON_PASSWORDS_FILE", tmp_path / "gone.txt")

    with pytest.raises(FileNotFoundError):
        security._load_common_passwords()


# ── the rule ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("password", REFUSED + ADMIN_REFUSED)
def test_a_weak_password_is_refused(password: str) -> None:
    assert is_common_password(password) or is_patterned_password(password)


@pytest.mark.parametrize("password", ACCEPTED)
def test_a_good_password_is_let_through(password: str) -> None:
    assert not is_common_password(password)
    assert not is_patterned_password(password)


@pytest.mark.parametrize("password", ["Password1!", "monkey2024!", "  summer  ", "#Dragon99"])
def test_a_decorated_common_word_counts_as_the_word(password: str) -> None:
    assert is_common_password(password)


def test_only_the_whole_core_is_looked_up() -> None:
    """`password` inside a longer phrase is not `password`."""
    assert not is_common_password("Password-Tbilisi-1!")
    assert not is_common_password("my password is long 1")


def test_a_core_too_short_to_mean_anything_is_not_looked_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard on the trimmed look-up, against a list that gains short words."""
    monkeypatch.setattr(security, "COMMON_PASSWORDS", COMMON_PASSWORDS | {"ab", "abc"})

    assert not is_common_password("ab!!!!!!12")
    assert not is_common_password("abc!9#7$5%")
    # The whole password is still compared as it is, short or not.
    assert is_common_password("abc")


def test_five_different_characters_must_be_left_after_the_patterns() -> None:
    assert not is_patterned_password("abcdexk9zq")  # x k 9 z q
    assert is_patterned_password("abcdexk9zz")  # x k 9 z


def test_a_step_across_kinds_of_character_is_not_a_sequence() -> None:
    assert not security._is_pattern("9", ":", ";")
    assert not security._is_pattern("a", "c", "e")
    assert security._is_pattern("c", "b", "a")
    assert security._is_pattern("3", "2", "1")


# ── applied where a new password is set ──────────────────────────────────────


@pytest.mark.parametrize("password", REFUSED)
async def test_register_refuses_a_weak_password(client: httpx.AsyncClient, password: str) -> None:
    response = await client.post(
        REGISTER,
        json={
            "firstName": "ნინო",
            "lastName": "კაპანაძე",
            "email": "weak@example.ge",
            "password": password,
        },
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["field"] == "password"


@pytest.mark.parametrize("password", ["Tbilisi-Vake-2026", "k7#Rm2!pQz", "mzeqalaqi-ghame-77"])
async def test_register_accepts_a_good_password(client: httpx.AsyncClient, password: str) -> None:
    response = await client.post(
        REGISTER,
        json={
            "firstName": "ნინო",
            "lastName": "კაპანაძე",
            "email": "good@example.ge",
            "password": password,
        },
    )

    assert response.status_code == 201


@pytest.mark.parametrize("password", REFUSED)
async def test_change_password_refuses_a_weak_one(
    client: httpx.AsyncClient, db: AsyncSession, password: str
) -> None:
    user = await make_user(db)

    response = await client.post(
        CHANGE,
        headers=auth_header(user),
        json={"currentPassword": "supersecret1", "newPassword": password},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("password", REFUSED)
async def test_reset_password_refuses_a_weak_one(
    client: httpx.AsyncClient, db: AsyncSession, password: str
) -> None:
    user = await make_user(db)
    issued = await auth_service.issue_password_reset(db, email=user.email)
    assert issued is not None

    response = await client.post(RESET, json={"token": issued.token, "newPassword": password})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    # The refusal did not spend the link: a better password works on it.
    retry = await client.post(
        RESET, json={"token": issued.token, "newPassword": "Tbilisi-Vake-2026"}
    )
    assert retry.status_code == 200


# ── what is never touched: signing in with a password chosen before ──────────


@pytest.mark.parametrize("password", ["aaaaaaaa", "12345678", "Password1!", "abcd1234", "x"])
@pytest.mark.parametrize("role", [ROLE_CUSTOMER, ROLE_ADMIN])
async def test_an_existing_weak_password_still_signs_in(
    client: httpx.AsyncClient, db: AsyncSession, password: str, role: str
) -> None:
    """The rule is for a new password; login never asks whether the old one passes it."""
    await make_user(db, email="old@example.ge", password=password, role=role)

    response = await client.post(LOGIN, json={"email": "old@example.ge", "password": password})

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "old@example.ge"


async def test_a_weak_wrong_password_at_login_is_a_401_not_a_validation_error(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await make_user(db, email="old@example.ge")

    response = await client.post(LOGIN, json={"email": "old@example.ge", "password": "aaaaaaaa"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


# ── the administrator's twelve ───────────────────────────────────────────────

#: Strong, and eleven and twelve characters long.
ELEVEN = "k7#Rm2!pQzW"
TWELVE = "k7#Rm2!pQzWx"


def test_the_two_strong_samples_are_the_lengths_they_claim() -> None:
    assert (len(ELEVEN), len(TWELVE)) == (MIN_ADMIN_PASSWORD_LENGTH - 1, MIN_ADMIN_PASSWORD_LENGTH)
    for sample in (ELEVEN, TWELVE):
        assert not is_common_password(sample)
        assert not is_patterned_password(sample)


async def test_an_admin_cannot_change_to_eleven_characters(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    admin = await make_user(db, email="boss@example.ge", role=ROLE_ADMIN)

    response = await client.post(
        CHANGE,
        headers=auth_header(admin),
        json={"currentPassword": "supersecret1", "newPassword": ELEVEN},
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "ADMIN_PASSWORD_TOO_SHORT"
    assert error["details"][0]["field"] == "newPassword"
    # Nothing changed: the old password still opens the account.
    stored = await db.scalar(select(User.password_hash).where(User.id == admin.id))
    assert stored is not None
    assert verify_password("supersecret1", stored)
    # And a refusal for length is not a guess at the current password.
    await db.refresh(admin)
    assert admin.failed_login_count == 0


async def test_an_admin_can_change_to_twelve_characters(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    admin = await make_user(db, email="boss@example.ge", role=ROLE_ADMIN)

    response = await client.post(
        CHANGE,
        headers=auth_header(admin),
        json={"currentPassword": "supersecret1", "newPassword": TWELVE},
    )

    assert response.status_code == 200
    login = await client.post(LOGIN, json={"email": "boss@example.ge", "password": TWELVE})
    assert login.status_code == 200


async def test_a_customers_minimum_stays_eight(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await make_user(db, email="buyer@example.ge")

    response = await client.post(
        CHANGE,
        headers=auth_header(user),
        json={"currentPassword": "supersecret1", "newPassword": "k7#Rm2!p"},
    )

    assert response.status_code == 200


async def test_an_admin_cannot_reset_to_eleven_characters_but_the_link_survives(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    admin = await make_user(db, email="boss@example.ge", role=ROLE_ADMIN)
    issued = await auth_service.issue_password_reset(db, email=admin.email)
    assert issued is not None

    refused = await client.post(RESET, json={"token": issued.token, "newPassword": ELEVEN})

    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "ADMIN_PASSWORD_TOO_SHORT"
    stored = await db.scalar(select(User.password_hash).where(User.id == admin.id))
    assert stored is not None
    assert verify_password("supersecret1", stored)

    # The same link, a longer password.
    accepted = await client.post(RESET, json={"token": issued.token, "newPassword": TWELVE})
    assert accepted.status_code == 200
    login = await client.post(LOGIN, json={"email": "boss@example.ge", "password": TWELVE})
    assert login.status_code == 200


async def test_a_customer_can_reset_to_eight_characters(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    user = await make_user(db, email="buyer@example.ge")
    issued = await auth_service.issue_password_reset(db, email=user.email)
    assert issued is not None

    response = await client.post(RESET, json={"token": issued.token, "newPassword": "k7#Rm2!p"})

    assert response.status_code == 200


async def test_a_bad_link_is_still_an_invalid_link_whatever_the_password(
    client: httpx.AsyncClient,
) -> None:
    """The admin check sits behind the link: it tells nobody who is an admin."""
    response = await client.post(RESET, json={"token": "x" * 43, "newPassword": ELEVEN})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_RESET_TOKEN"
