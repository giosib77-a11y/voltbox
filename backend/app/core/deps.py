"""საერთო FastAPI dependency-ები."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
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
    return user


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
