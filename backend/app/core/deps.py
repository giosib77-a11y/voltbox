"""საერთო FastAPI dependency-ები."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import VERSION_CLAIM, decode_access_token
from app.db.models import ROLE_ADMIN, User
from app.db.session import get_db

# auto_error=False — თავად ვაბრუნებთ შეცდომას ჩვენი კონვერტით,
# თორემ FastAPI-ს ნაგულისხმევი {"detail": ...} გაიპარებოდა
bearer_scheme = HTTPBearer(auto_error=False, description="Bearer <access token>")

Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
Db = Annotated[AsyncSession, Depends(get_db)]


async def _user_from_credentials(credentials: Credentials, db: AsyncSession) -> User | None:
    if credentials is None or not credentials.credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return None
    try:
        user_id = UUID(str(payload.get("sub")))
    except (ValueError, TypeError):
        return None

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        return None
    if _revoked(payload, user):
        return None
    return user


def _revoked(payload: dict[str, Any], user: User) -> bool:
    """Whether the account has invalidated its tokens since this one was issued.

    An access token cannot be taken back on its own - it is a signed statement
    with a 30 minute life. Revoking the refresh tokens stops a session being
    extended and does nothing about the access token already handed out, so
    changing a stolen password left the thief the rest of that half hour. This
    is the check that closes it, and it is free: the row is already loaded.

    A version rather than an issued-before-this-instant comparison, because
    `iat` is whole seconds - a token minted in the same second as the revocation
    could not be told from one minted just before it.
    """
    version = payload.get(VERSION_CLAIM)
    if not isinstance(version, int) or isinstance(version, bool):
        # Every token this application mints carries one. A token without it
        # was either minted before this existed or not by us; neither is a
        # reason to trust it.
        return True
    return version != user.token_version


async def get_current_user(credentials: Credentials, db: Db) -> User:
    """სავალდებულო ავტორიზაცია — 401 ყველა წარუმატებელ შემთხვევაზე."""
    user = await _user_from_credentials(credentials, db)
    if user is None:
        raise UnauthorizedError("Invalid or expired token", code="INVALID_TOKEN")
    return user


async def get_optional_user(credentials: Credentials, db: Db) -> User | None:
    """არასავალდებულო ავტორიზაცია.

    სტუმრის checkout-ისთვის: ტოკენის არარსებობა ან უვარგისობა შეცდომა არაა —
    შეკვეთა ორივე შემთხვევაში უნდა გაფორმდეს.
    """
    return await _user_from_credentials(credentials, db)


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


async def require_admin(user: CurrentUser) -> User:
    """Administrator-only access.

    Composed on top of `get_current_user`, which already loads the row from the
    database and rejects an inactive account on every request. That is what
    makes a demotion or a block take effect immediately instead of when the
    30-minute access token happens to expire - the role is never trusted from
    the JWT payload.

    Raises 403 for an authenticated non-admin, and 401 for anyone unauthenticated
    (raised earlier, by `get_current_user`).
    """
    if user.role != ROLE_ADMIN:
        raise ForbiddenError("Administrator access required", code="ADMIN_REQUIRED")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
