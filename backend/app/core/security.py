"""პაროლების ჰეშირება და JWT-ტოკენები.

Argon2id — OWASP-ის რეკომენდებული ალგორითმი პაროლებისთვის. bcrypt-ისგან
განსხვავებით მეხსიერებაზეც მძიმეა, რაც GPU-შეტევებს აძვირებს.

refresh-ტოკენი ბაზაში მხოლოდ SHA-256 hash-ის სახით ინახება: ბაზის გაჟონვისას
ნედლი ტოკენები გამოუყენებელი რჩება. hash-ი აქ განზრახ სწრაფია (და არა Argon2) —
ტოკენი 384-ბიტიანი (`token_urlsafe(48)`) შემთხვევითი მნიშვნელობაა, სიტყვების
ლექსიკონით არ იტეხება.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()

#: SecLists' 10k most common passwords, byte for byte; the source, commit, hash
#: and MIT notice are in common_passwords.NOTICE.txt beside it. A data file in
#: the package tree, so the wheel and `COPY app ./app` both carry it.
_COMMON_PASSWORDS_FILE = Path(__file__).with_name("common_passwords.txt")

#: What this shop adds to the list: its own market, and the short obvious ones
#: it has always refused. Kept here, not in the file, so the file stays
#: identical to upstream and its hash stays checkable.
_SHOP_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "12345678",
        "123456789",
        "1234567890",
        "qwerty123",
        "password1",
        "11111111",
        "abc12345",
        "iloveyou",
        "admin123",
        "welcome1",
        "letmein1",
        "qwertyui",
        "password123",
        "1qaz2wsx",
        "georgia1",
        "sakartvelo",
    }
)


def _load_common_passwords() -> frozenset[str]:
    """Lower-cased, once, at import. A missing file raises here, so a build that
    forgot to ship it fails to start instead of quietly accepting `123456`."""
    lines = _COMMON_PASSWORDS_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip().lower() for line in lines if line.strip()) | (
        _SHOP_COMMON_PASSWORDS
    )


COMMON_PASSWORDS = _load_common_passwords()
MIN_PASSWORD_LENGTH = 8
#: An administrator's panel shows every buyer's name, phone, address and orders,
#: and signs in with a password alone, so theirs has to be longer.
MIN_ADMIN_PASSWORD_LENGTH = 12


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


#: One Argon2 run at a time per worker, as when it ran on the event loop.
#:
#: Each run takes 64 MiB (argon2-cffi's default memory_cost) for its ~120 ms.
#: The event loop used to bound that to one by stalling everything else; a
#: thread pool bounds it to the pool's size - dozens - which is gigabytes the
#: free plan does not have. One keeps the memory ceiling where it was, and more
#: would not finish more hashes a second on the fraction of a CPU it gets.
_HASHING = asyncio.Semaphore(1)


async def hash_password_async(password: str) -> str:
    """`hash_password` in a thread, so the event loop serves other requests meanwhile.

    The GIL is no obstacle: argon2-cffi runs the hash in C through cffi, which
    releases it for the call.
    """
    async with _HASHING:
        return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, password_hash: str) -> bool:
    """`verify_password` in a thread, for the same reason as `hash_password_async`."""
    async with _HASHING:
        return await asyncio.to_thread(verify_password, password, password_hash)


#: Shortest core worth looking up. The list's own shortest entries are four
#: characters, so today this only keeps it that way: should a later update of
#: the list bring in one- to three-letter words, `ab!!!!!!12` would otherwise
#: be refused for starting with `ab`, which says nothing about the password.
_MIN_CORE_LENGTH = 4

#: Dropped from both ends before the second look-up: what people append to a
#: word to satisfy a "digit and symbol" rule (`Password1!`, `monkey2024!`).
_DECORATION = string.digits + string.punctuation + string.whitespace

#: The same without the digits, for the look-up that keeps them.
_PUNCTUATION_ONLY = string.punctuation + string.whitespace


def is_common_password(password: str) -> bool:
    """True when the password is on the common list, bare or merely decorated.

    Three look-ups, all lower-cased: the whole password; the password with
    punctuation and spaces trimmed off both ends (`1q2w3e4r!` is `1q2w3e4r`);
    and the password with digits trimmed as well - so `Password1!` is
    `password`, and `monkey2024!` is `monkey`. Both trimmed forms count only
    from `_MIN_CORE_LENGTH` characters, and only when they are the *whole* core:
    `Tbilisi-Vake-2026` trims to `tbilisi-vake`, which is not on the list.
    The digit-keeping form is needed because a word that starts or ends in a
    digit is not itself once the digit is gone (`q2w3e4r` is on no list).
    """
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS:
        return True
    # Punctuation and spaces only: a digit at an edge can belong to the word
    # (`1q2w3e4r!` is `1q2w3e4r`, which is listed; digits-too trims it to `q2w3e4r`).
    for decoration in (_PUNCTUATION_ONLY, _DECORATION):
        core = lowered.strip(decoration)
        if len(core) >= _MIN_CORE_LENGTH and core in COMMON_PASSWORDS:
            return True
    return False


#: Rows of a keyboard. Three keys in a row, in either direction, are a pattern.
_KEYBOARD_ROWS = ("1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm")
_KEYBOARD_TRIPLES = frozenset(
    run[i : i + 3]
    for row in _KEYBOARD_ROWS
    for run in (row, row[::-1])
    for i in range(len(row) - 2)
)

#: Where each key sits on a standard staggered QWERTY keyboard: (row, x), x in
#: quarters of a key width. The rows are shifted by half a key (q against 1),
#: a quarter (a against q) and half a key (z against a), so q sits between 1
#: and 2, and a between q and w.
_ROW_SHIFT = (0, 2, 3, 5)
_KEY_POSITION = {
    char: (row, 4 * column + _ROW_SHIFT[row])
    for row, keys in enumerate(_KEYBOARD_ROWS)
    for column, char in enumerate(keys)
}


def _vertical_neighbours(a: str, b: str) -> bool:
    """Keys in adjacent rows that touch: closer than one key width sideways."""
    (row_a, x_a), (row_b, x_b) = _KEY_POSITION[a], _KEY_POSITION[b]
    return abs(row_a - row_b) == 1 and abs(x_a - x_b) < 4


def _is_keyboard_walk(a: str, b: str, c: str) -> bool:
    """Three keys that are one finger-movement across two neighbouring rows.

    Two shapes, both between rows that touch, neither a plain run along one row
    (that is `_KEYBOARD_TRIPLES`):
    - down or up a column, or a zigzag that keeps going the same way sideways:
      `1qa`, `qaz`, `zaq`, `1q2`, `q2w`, `wsx`. Each step is to a key that
      touches, and both steps go the same way sideways, so `qaq` and `q1q` do not
      count.
    - the pairs people type across two rows: `q1w`, `w2e` - the outer two are
      neighbours on one row and the middle one touches either of them. (`1q2`
      is this shape as well as the first.)
    Keys that are not letters or digits are never part of it.
    """
    if not all(char in _KEY_POSITION for char in (a, b, c)):
        return False
    (row_a, x_a), (_, x_b), (row_c, x_c) = _KEY_POSITION[a], _KEY_POSITION[b], _KEY_POSITION[c]
    keeps_going = (x_b - x_a) * (x_c - x_b) > 0
    if keeps_going and _vertical_neighbours(a, b) and _vertical_neighbours(b, c):
        return True
    return (
        row_a == row_c
        and abs(x_a - x_c) == 4
        and (_vertical_neighbours(a, b) or _vertical_neighbours(b, c))
    )


#: How many different characters must be left once the patterns are taken out.
MIN_DISTINCT_CHARACTERS = 5


def _is_digit(char: str) -> bool:
    return "0" <= char <= "9"


def _is_pattern(a: str, b: str, c: str) -> bool:
    """Three characters that are one character, a step of one, or three adjacent keys."""
    if a == b == c or a + b + c in _KEYBOARD_TRIPLES or _is_keyboard_walk(a, b, c):
        return True
    step = ord(b) - ord(a)
    if step not in (1, -1) or ord(c) - ord(b) != step:
        return False
    # Digits with digits and letters with letters: `9:;` is consecutive in
    # Unicode and means nothing.
    return all(map(_is_digit, (a, b, c))) or (a.isalpha() and b.isalpha() and c.isalpha())


def is_patterned_password(password: str) -> bool:
    """True when the password is a repetition or a sequence with a little added.

    The rule: take out every character that belongs to a run of three or more
    that is the same character (`aaa`), a step of one in the alphabet or among
    the digits, up or down (`abc`, `321`), or neighbouring keys of a keyboard
    row, either way (`qwe`, `rewq`), or a walk across two touching rows of a
    keyboard (`1q2`, `q1w`, `qaz`, `wsx`: see `_is_keyboard_walk`). What is left
    must contain at least `MIN_DISTINCT_CHARACTERS` different characters, case
    ignored. So `aaaaaaaa`, `12345678`, `hgfedcba`, `qwertyuiop`, `12345678a`,
    `aaaaaaaa1`, `1q2w3e4r!` and `1qaz2wsx` leave 0 or 1 and are refused;
    `Tbilisi-Vake-2026` loses nothing, and a random `Xv9$kLm2#qRz` loses only
    `klm`.

    A pattern anywhere is removed, not only at the ends, but nothing else is
    estimated: this is a filter for the lazy, not a measure of strength.
    """
    lowered = password.lower()
    in_pattern: set[int] = set()
    for i in range(len(lowered) - 2):
        if _is_pattern(lowered[i], lowered[i + 1], lowered[i + 2]):
            in_pattern.update((i, i + 1, i + 2))
    left = {char for i, char in enumerate(lowered) if i not in in_pattern}
    return len(left) < MIN_DISTINCT_CHARACTERS


#: Claim carrying the account's token version at the moment of issue. Compared
#: against the stored one on every request; a mismatch means the account has
#: invalidated its tokens since, and this is one of them.
VERSION_CLAIM = "tv"


def create_access_token(user_id: uuid.UUID, token_version: int = 0) -> tuple[str, datetime]:
    """წვდომის ტოკენი. `jti` საჭიროა მომავალი revocation-ისთვის."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
        VERSION_CLAIM: token_version,
        "type": "access",
    }
    token = jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any] | None:
    """`None` ნიშნავს „არასწორი, ვადაგასული ან სხვა ტიპის ტოკენი“."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret.get_secret_value(), algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


def generate_refresh_token() -> tuple[str, str, datetime]:
    """→ (ნედლი ტოკენი, მისი hash, ვადა). ნედლი მხოლოდ კლიენტს უბრუნდება."""
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)
    return raw, hash_refresh_token(raw), expires_at


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


#: How long a password reset link works. Long enough to find the email and
#: open it, short enough that a link left in a mailbox is soon worth nothing.
PASSWORD_RESET_TTL = timedelta(minutes=30)


def generate_password_reset_token() -> tuple[str, str]:
    """→ (the raw token, its hash). The raw one goes into the email and nowhere else."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_password_reset_token(raw)


def hash_password_reset_token(raw: str) -> str:
    """The same SHA-256 as a refresh token's, for the same reason.

    256 random bits cannot be guessed from a dictionary, so a fast hash is
    enough, and a leaked table holds nothing that opens a link.
    """
    return hash_refresh_token(raw)


def generate_order_lookup_token() -> tuple[str, str]:
    """→ (the raw token, its hash). The raw one goes to the guest's browser, once.

    What lets a guest read their order. The order number is sequential and the
    phone is known to anyone the shopper has given it to, so neither can be the
    secret; 256 random bits can.
    """
    raw = secrets.token_urlsafe(32)
    return raw, hash_order_lookup_token(raw)


def hash_order_lookup_token(raw: str) -> str:
    """The same SHA-256 as a password reset token's, for the same reason."""
    return hash_refresh_token(raw)


TokenType = Literal["access", "refresh"]
