"""ავტორიზაციის მარშრუტები.

The refresh token lives in an httpOnly cookie and nowhere else: not in the JSON
body, not in a request body, not in localStorage. What that buys is narrow and
worth stating exactly - script running on the page can still *use* the session,
because the browser attaches the cookie for it, but it cannot read the token and
send it somewhere. An XSS then lasts as long as the tab is open instead of a
month from anywhere.
"""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Cookie, Request, Response, status

from app.core.config import settings
from app.core.deps import CurrentUser, Db
from app.core.errors import AppError, UnauthorizedError
from app.core.rate_limit import (
    AUTH_RATE_LIMIT,
    RESET_EMAIL_ADDRESS_LIMIT,
    hit_per_address,
    limiter,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    OkOut,
    RegisterRequest,
    ResetPasswordRequest,
    SessionOut,
    UpdateProfileRequest,
    UserOut,
)
from app.services import auth as auth_service
from app.services import password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])

#: The cookie as the browser sees it. Read from one place so that setting it and
#: deleting it can never drift - a delete with a different Path is ignored, and
#: the session would outlive the logout that was supposed to end it.
RefreshCookie = Annotated[str | None, Cookie(alias=settings.refresh_cookie_name)]


def _attach_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        settings.refresh_cookie_name,
        raw_token,
        max_age=settings.refresh_cookie_max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path=settings.cookie_path,
        # No Domain: the cookie then belongs to this host alone and is not
        # shared with any sibling subdomain.
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Must match how it was set, Path included, or the browser keeps it."""
    response.delete_cookie(
        settings.refresh_cookie_name,
        path=settings.cookie_path,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )


def _session(payload: dict[str, Any], response: Response) -> SessionOut:
    """Body for the client, cookie for the browser."""
    _attach_refresh_cookie(response, str(payload["refresh_token"]))
    return SessionOut(
        user=UserOut.model_validate(payload["user"]),
        token=str(payload["token"]),
        expires_at=payload["expires_at"],
    )


@router.post(
    "/register",
    summary="Register a new account",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionOut,
)
@limiter.limit(AUTH_RATE_LIMIT)
async def register(
    request: Request, response: Response, db: Db, payload: RegisterRequest
) -> SessionOut:
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
    return _session(session, response)


@router.post("/login", summary="Log in", response_model=SessionOut)
@limiter.limit(AUTH_RATE_LIMIT)
async def login(request: Request, response: Response, db: Db, payload: LoginRequest) -> SessionOut:
    try:
        session = await auth_service.login(db, email=payload.email, password=payload.password)
    except UnauthorizedError:
        # The failed attempt has to outlive the request that failed. `get_db`
        # rolls back on an exception, which would discard the count that decides
        # when to lock the account - so a thousand wrong passwords would each
        # roll back their own evidence and the lock would never arrive.
        await db.commit()
        raise
    await db.commit()
    return _session(session, response)


@router.post(
    "/refresh",
    summary="Exchange the refresh cookie for a new session",
    description=(
        "Takes no body. The refresh token is read from the httpOnly cookie set "
        "at login, so a caller that can read JavaScript cannot supply one."
    ),
    response_model=SessionOut,
)
@limiter.limit(AUTH_RATE_LIMIT)
async def refresh(
    request: Request, response: Response, db: Db, refresh_token: RefreshCookie = None
) -> SessionOut:
    if not refresh_token:
        # Same answer as a token that is expired or already spent: whether a
        # cookie was sent is not information worth handing out.
        _clear_refresh_cookie(response)
        raise auth_service.invalid_refresh_token()
    session = await auth_service.refresh(db, raw_token=refresh_token)
    await db.commit()
    return _session(session, response)


@router.post("/logout", summary="Log out", response_model=OkOut)
async def logout(db: Db, response: Response, refresh_token: RefreshCookie = None) -> OkOut:
    # ქართული ახსნა: ტოკენის გარეშეც 200-ს ვაბრუნებთ — გასვლა იდემპოტენტურია
    # და კლიენტს არ უნდა შეეშალოს, თუ ტოკენი უკვე დაკარგულია
    await auth_service.logout(db, raw_token=refresh_token)
    await db.commit()
    # Revoked in the database *and* removed from the browser. Either one alone
    # leaves a logout that did not log anything out.
    _clear_refresh_cookie(response)
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


@router.post(
    "/forgot-password",
    summary="Email a password reset link",
    description=(
        "The same 200 whether or not the address has an account, after the same "
        "work: the link is emailed after the response. 503 while the shop cannot "
        "send email - the storefront hides the link then (GET /delivery, "
        "`features.email`). 429 per IP, and per address whether or not it is "
        "registered."
    ),
    response_model=OkOut,
)
@limiter.limit(AUTH_RATE_LIMIT)
async def forgot_password(
    request: Request, db: Db, payload: ForgotPasswordRequest, background: BackgroundTasks
) -> OkOut:
    # `request` is what slowapi reads the client address from. Unused here.
    if not settings.order_email_enabled:
        # A 200 here would promise an email that cannot go. Nothing about the
        # address has been looked at, so this says nothing about it either.
        raise AppError(
            "Password reset is unavailable",
            code="PASSWORD_RESET_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if not hit_per_address(
        RESET_EMAIL_ADDRESS_LIMIT, scope="password-reset", address=payload.email
    ):
        raise AppError(
            "Too many password reset requests for this address",
            code="TOO_MANY_RESET_REQUESTS",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    issued = await auth_service.issue_password_reset(db, email=payload.email)
    # Committed whichever the answer - see issue_password_reset.
    await db.commit()
    if issued is not None:
        background.add_task(
            password_reset_email.send_link,
            password_reset_email.ResetLink(
                user_id=issued.user_id,
                recipient=payload.email.strip().lower(),
                token=issued.token,
            ),
        )
    return OkOut()


@router.post(
    "/reset-password",
    summary="Set a new password with a reset link",
    description=(
        "Takes the token from the link and a new password under the registration "
        "rules. A link works once and for 30 minutes; a used, expired or "
        "replaced one is a 400 INVALID_RESET_TOKEN. Success ends every session "
        "of the account, on every device."
    ),
    response_model=OkOut,
)
@limiter.limit(AUTH_RATE_LIMIT)
async def reset_password(request: Request, db: Db, payload: ResetPasswordRequest) -> OkOut:
    # `request` is what slowapi reads the client address from. Unused here.
    await auth_service.reset_password(
        db, raw_token=payload.token, new_password=payload.new_password
    )
    await db.commit()
    return OkOut()
