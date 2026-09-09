"""ავტორიზაციის ბიზნეს-ლოგიკა.

refresh-ტოკენები rotation-on-use პრინციპით მუშაობს: ყოველი გამოყენებისას ძველი
უქმდება და ახალი გაიცემა. ეს ტოკენის მოპარვას ამჩნევს — თუ მოპარული ტოკენი
უკვე გამოყენებულია, მეორედ აღარ იმუშავებს.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, UnauthorizedError, ValidationError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.models import RefreshToken, User

# წარუმატებელი შესვლისას ყოველთვის ერთი და იგივე ტექსტი: არსებული და
# არარსებული ელ. ფოსტის გარჩევა მომხმარებელთა ბაზის აღრიცხვის საშუალებას მისცემდა
INVALID_CREDENTIALS = "Invalid email or password"

# დროის მუდმივობისთვის: არარსებულ მომხმარებელზეც ვასრულებთ ჰეშის შემოწმებას,
# რომ პასუხის დრო არსებობას არ ამხელდეს
_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHR2YWx1ZQ$0000000000000000000000000000000000000000000"
)


async def _issue_session(db: AsyncSession, user: User) -> dict[str, object]:
    access_token, expires_at = create_access_token(user.id)
    raw_refresh, refresh_hash, refresh_expires = generate_refresh_token()

    db.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=refresh_expires))
    await db.flush()

    return {
        "user": user,
        "token": access_token,
        "refresh_token": raw_refresh,
        "expires_at": expires_at,
    }


async def register(
    db: AsyncSession, *, first_name: str, last_name: str, email: str, password: str
) -> dict[str, object]:
    normalized = email.strip().lower()
    existing = await db.scalar(select(User).where(User.email == normalized))
    if existing is not None:
        raise ConflictError("Email is already registered", code="EMAIL_ALREADY_EXISTS")

    user = User(
        email=normalized,
        password_hash=hash_password(password),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
    )
    db.add(user)
    await db.flush()
    return await _issue_session(db, user)


async def login(db: AsyncSession, *, email: str, password: str) -> dict[str, object]:
    user = await db.scalar(select(User).where(User.email == email.strip().lower()))

    if user is None:
        verify_password(password, _DUMMY_HASH)  # დროის გათანაბრება
        raise UnauthorizedError(INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")
    if not verify_password(password, user.password_hash):
        raise UnauthorizedError(INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled", code="ACCOUNT_DISABLED")

    return await _issue_session(db, user)


async def refresh(db: AsyncSession, *, raw_token: str) -> dict[str, object]:
    token_hash = hash_refresh_token(raw_token)
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    now = datetime.now(UTC)
    if stored is None or stored.revoked_at is not None or stored.expires_at <= now:
        raise UnauthorizedError("Refresh token is invalid or expired", code="INVALID_REFRESH_TOKEN")

    user = await db.scalar(select(User).where(User.id == stored.user_id))
    if user is None or not user.is_active:
        raise UnauthorizedError("Account is not available", code="ACCOUNT_DISABLED")

    stored.revoked_at = now  # rotation: ძველი მაშინვე უქმდება
    await db.flush()
    return await _issue_session(db, user)


async def logout(db: AsyncSession, *, raw_token: str | None) -> None:
    """გასვლა refresh-ტოკენს ბაზაში აუქმებს.

    კლიენტის მხარეს ტოკენის წაშლა საკმარისი არაა — მოპარული refresh-ტოკენი
    სერვერზე მაინც მოქმედი დარჩებოდა.
    """
    if not raw_token:
        return
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(raw_token),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )


async def revoke_all(db: AsyncSession, user_id: object) -> None:
    """პაროლის შეცვლისას ყველა სესია უნდა გაითიშოს."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def change_password(
    db: AsyncSession, *, user: User, current_password: str, new_password: str
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise ValidationError(
            "Current password is incorrect",
            code="INVALID_CURRENT_PASSWORD",
            details=[{"field": "currentPassword", "message": "Current password is incorrect"}],
        )
    user.password_hash = hash_password(new_password)
    await db.flush()
    await revoke_all(db, user.id)


async def update_profile(db: AsyncSession, *, user: User, changes: dict[str, object]) -> User:
    if (email := changes.get("email")) is not None:
        normalized = str(email).strip().lower()
        if normalized != user.email:
            taken = await db.scalar(
                select(User).where(User.email == normalized, User.id != user.id)
            )
            if taken is not None:
                raise ConflictError("Email is already registered", code="EMAIL_ALREADY_EXISTS")
        user.email = normalized

    for field in ("first_name", "last_name", "phone"):
        if (value := changes.get(field)) is not None:
            setattr(user, field, str(value).strip())

    await db.flush()
    return user
