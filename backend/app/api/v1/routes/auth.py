"""ავტორიზაციის მარშრუტები."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Request, status

from app.core.deps import CurrentUser, Db
from app.core.rate_limit import AUTH_RATE_LIMIT, limiter
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    OkOut,
    RefreshRequest,
    RegisterRequest,
    SessionOut,
    UpdateProfileRequest,
    UserOut,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _session(payload: dict[str, Any]) -> SessionOut:
    return SessionOut(
        user=UserOut.model_validate(payload["user"]),
        token=str(payload["token"]),
        refresh_token=str(payload["refresh_token"]),
        expires_at=payload["expires_at"],
    )


@router.post(
    "/register",
    summary="Register a new account",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionOut,
)
@limiter.limit(AUTH_RATE_LIMIT)
async def register(request: Request, db: Db, payload: RegisterRequest) -> SessionOut:
    # ქართული ახსნა: `request` პარამეტრი slowapi-ს სჭირდება IP-ის ამოსაცნობად —
    # ხელით არსად არ გამოიყენება, მაგრამ ხელმოწერიდან ვერ მოვხსნით
    session = await auth_service.register(
        db,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        password=payload.password,
    )
    await db.commit()
    return _session(session)


@router.post("/login", summary="Log in", response_model=SessionOut)
@limiter.limit(AUTH_RATE_LIMIT)
async def login(request: Request, db: Db, payload: LoginRequest) -> SessionOut:
    session = await auth_service.login(db, email=payload.email, password=payload.password)
    await db.commit()
    return _session(session)


@router.post("/refresh", summary="Exchange a refresh token", response_model=SessionOut)
@limiter.limit(AUTH_RATE_LIMIT)
async def refresh(request: Request, db: Db, payload: RefreshRequest) -> SessionOut:
    session = await auth_service.refresh(db, raw_token=payload.refresh_token)
    await db.commit()
    return _session(session)


@router.post("/logout", summary="Log out", response_model=OkOut)
async def logout(
    db: Db,
    refresh_token: Annotated[str | None, Body(embed=True, alias="refreshToken")] = None,
) -> OkOut:
    # ქართული ახსნა: ტოკენის გარეშეც 200-ს ვაბრუნებთ — გასვლა იდემპოტენტურია
    # და კლიენტს არ უნდა შეეშალოს, თუ ტოკენი უკვე დაკარგულია
    await auth_service.logout(db, raw_token=refresh_token)
    await db.commit()
    return OkOut()


@router.get("/me", summary="Current user profile", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", summary="Update the current profile", response_model=UserOut)
async def update_me(db: Db, user: CurrentUser, payload: UpdateProfileRequest) -> UserOut:
    updated = await auth_service.update_profile(
        db, user=user, changes=payload.model_dump(exclude_unset=True)
    )
    await db.commit()
    return UserOut.model_validate(updated)


@router.post("/change-password", summary="Change the password", response_model=OkOut)
async def change_password(db: Db, user: CurrentUser, payload: ChangePasswordRequest) -> OkOut:
    await auth_service.change_password(
        db,
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    await db.commit()
    return OkOut()
