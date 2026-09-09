"""პაროლების ჰეშირება და JWT-ტოკენები.

Argon2id — OWASP-ის რეკომენდებული ალგორითმი პაროლებისთვის. bcrypt-ისგან
განსხვავებით მეხსიერებაზეც მძიმეა, რაც GPU-შეტევებს აძვირებს.

refresh-ტოკენი ბაზაში მხოლოდ SHA-256 hash-ის სახით ინახება: ბაზის გაჟონვისას
ნედლი ტოკენები გამოუყენებელი რჩება. hash-ი აქ განზრახ სწრაფია (და არა Argon2) —
ტოკენი 256-ბიტიანი შემთხვევითი მნიშვნელობაა, სიტყვების ლექსიკონით არ იტეხება.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()

# ყველაზე გავრცელებული პაროლები — რეგისტრაციაზე უარვყოფთ
COMMON_PASSWORDS = frozenset(
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
MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def is_common_password(password: str) -> bool:
    return password.lower() in COMMON_PASSWORDS


def create_access_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    """წვდომის ტოკენი. `jti` საჭიროა მომავალი revocation-ისთვის."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any] | None:
    """`None` ნიშნავს „არასწორი, ვადაგასული ან სხვა ტიპის ტოკენი“."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
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


TokenType = Literal["access", "refresh"]
