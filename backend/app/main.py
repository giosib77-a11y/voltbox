"""FastAPI-ს app factory — middleware, შეცდომების დამმუშავებლები, მარშრუტები."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import error_body, register_exception_handlers
from app.core.headers import SecurityHeadersMiddleware
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.rate_limit import limiter
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    configure_logging()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="REST API for the VoltBox electronics store.",
        # Off wherever the API is reachable. The schema lists every admin route
        # with its request shape, which is a map worth not publishing.
        openapi_url=None if settings.is_deployed else "/openapi.json",
        docs_url=None if settings.is_deployed else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content=error_body("RATE_LIMITED", "Too many requests. Please try again later."),
        )

    # middleware-ის რიგი მნიშვნელოვანია: request_id ყველაზე გარეთ უნდა იყოს,
    # რომ CORS-ისა და შეცდომების პასუხებსაც მოხვდეს
    # Compression. Measured on this catalogue: a page of 48 products is 55 KB
    # uncompressed and 10 KB gzipped, and nothing was compressing it - the
    # browser asked and the API answered in full every time. Added innermost so
    # it sees the finished body.
    #
    # Safe here despite BREACH: that attack needs a secret in the response body
    # next to text the attacker controls. These responses carry no CSRF token,
    # and the one that returns a JWT - /auth/login - reflects nothing a caller
    # supplied. `minimum_size` keeps it off bodies too small to gain from it.
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
    )
    if settings.trusted_host_list != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)

    # Added last, so it sits outermost and the headers reach error responses and
    # CORS preflights too. A 500 is exactly when a browser should not improvise.
    app.add_middleware(SecurityHeadersMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
