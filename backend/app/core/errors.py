"""შეცდომების ერთიანი იერარქია და მათი HTTP-პასუხად გადაქცევა.

მთელი API ერთსა და იმავე კონვერტს აბრუნებს:

    {"error": {"code": "PRODUCT_NOT_FOUND", "message": "...", "details": null}}

`code` სტაბილური SCREAMING_SNAKE სტრიქონია — frontend სწორედ მასზე იტოტება,
ამიტომ ერთხელ დაფიქსირებული კოდი აღარ იცვლება (message-ის შეცვლა თავისუფალია).
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """ბაზისური აპლიკაციური შეცდომა — ყველა დანარჩენი აქედან მემკვიდრეობს."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"
    message: str = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: Any = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details
        self.status_code = status_code or self.status_code
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    message = "Resource not found"


class ValidationError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "VALIDATION_ERROR"
    message = "Invalid request"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"
    message = "Authentication required"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    message = "Not allowed"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"
    message = "Conflict"


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def _with_request_id(response: JSONResponse, request: Request) -> JSONResponse:
    """request_id პასუხშიც და header-შიც — ლოგებთან შესაბამისობისთვის."""
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        response = JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )
        return _with_request_id(response, request)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # ვალიდაციაზე FastAPI ნაგულისხმევად 422-ს აბრუნებს, frontend-ის კონტრაქტი კი
        # 400-ს ითხოვს — ამიტომ ვცვლით სტატუსსაც და კონვერტსაც.
        details = [
            {
                "field": ".".join(str(part) for part in err["loc"][1:]) or str(err["loc"][0]),
                "message": err["msg"],
                "type": err["type"],
            }
            for err in exc.errors()
        ]
        response = JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(error_body("VALIDATION_ERROR", "Invalid request", details)),
        )
        return _with_request_id(response, request)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            429: "RATE_LIMITED",
        }.get(exc.status_code, "HTTP_ERROR")
        response = JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, str(exc.detail)),
        )
        return _with_request_id(response, request)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # დეტალები ლოგში რჩება; კლიენტს არასდროს ვუბრუნებთ stack trace-ს
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body("INTERNAL_ERROR", "Internal server error"),
        )
        return _with_request_id(response, request)
