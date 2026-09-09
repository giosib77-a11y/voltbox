"""ავტორიზაციის request/response სქემები."""

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.core.security import MIN_PASSWORD_LENGTH, is_common_password
from app.schemas.base import ApiModel, ApiRequest


def _validate_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if is_common_password(value):
        raise ValueError("This password is too common")
    return value


class RegisterRequest(ApiRequest):
    first_name: str = Field(min_length=2, max_length=100)
    last_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(max_length=128)

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return _validate_password(value)


class LoginRequest(ApiRequest):
    email: EmailStr
    password: str = Field(max_length=128)


class RefreshRequest(ApiRequest):
    refresh_token: str = Field(min_length=16, max_length=256)


class ChangePasswordRequest(ApiRequest):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return _validate_password(value)


class UpdateProfileRequest(ApiRequest):
    first_name: str | None = Field(default=None, min_length=2, max_length=100)
    last_name: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)


class UserOut(ApiModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
    phone: str | None
    created_at: datetime


class SessionOut(ApiModel):
    """frontend `{ user, token }`-ს ელოდება და `session.token`-ს ინახავს.

    `refreshToken` დამატებითი ველია — არსებული კლიენტი მას უბრალოდ იგნორირებს,
    ახალი კი rotation-ისთვის გამოიყენებს.
    """

    user: UserOut
    token: str
    refresh_token: str
    expires_at: datetime


class OkOut(ApiModel):
    ok: bool = True
