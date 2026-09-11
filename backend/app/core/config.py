"""აპლიკაციის კონფიგურაცია — ერთადერთი ადგილი, სადაც გარემოს ცვლადები იკითხება.

ბიზნეს-წესებიც (მიწოდების ზღვარი, გვერდის ზომა, მარაგის ზღვარი) აქ ცხოვრობს,
რადგან ისინი frontend-ის კონსტანტებს უნდა ემთხვეოდეს — იხ. `../frontend/src/constants/index.js`.
განსხვავება ორ მხარეს შორის მდუმარე ბაგია, ამიტომ მნიშვნელობები აქ ერთადაა.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- environment ----------------------------------------------------------
    app_env: Literal["development", "staging", "production", "test"] = "development"
    app_name: str = "VoltBox API"
    api_v1_prefix: str = "/api/v1"

    # --- database -------------------------------------------------------------
    database_url: str
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    # იხ. app/db/ssl.py — რატომ არის `require` ნაგულისხმევი managed ბაზაზე
    db_ssl_mode: Literal["disable", "require", "verify-full"] = "require"
    db_ssl_root_cert: str = ""

    # --- auth -----------------------------------------------------------------
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30

    # --- refresh cookie -------------------------------------------------------
    # The refresh token is the long-lived credential, so it never reaches
    # JavaScript: httpOnly means an XSS can use the session while the page is
    # open but cannot copy the token out and keep it.
    refresh_cookie_name: str = "voltbox_refresh"
    # Scoped to the auth routes as the *browser* sees them. If a proxy serves
    # the API under a different external prefix, set this to that prefix -
    # otherwise the cookie is sent on the wrong paths, or on none.
    refresh_cookie_path: str = ""
    # Same-origin deployment (the frontend proxies /api to the backend), so the
    # strictest setting costs nothing. `none` would need CSRF protection.
    refresh_cookie_samesite: Literal["strict", "lax", "none"] = "strict"
    # None means "secure unless this is local development or a test run". A
    # Secure cookie is dropped outright over plain http, which would make every
    # local login - and every test - look like it silently failed.
    refresh_cookie_secure: bool | None = None

    # --- http -----------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://localhost:4173"
    trusted_hosts: str = "*"

    # --- rate limiting --------------------------------------------------------
    # Empty means in-process counters. Those are per worker, so with the two
    # gunicorn workers the Dockerfile starts, "5 logins per minute" silently
    # becomes ten. Set REDIS_URL for any deployment that runs more than one
    # process; see app/core/rate_limit.py for what happens when Redis is down.
    redis_url: str = ""

    # --- business rules (frontend-თან სინქრონში) ------------------------------
    shipping_free_threshold: int = 150
    shipping_flat_fee: int = 5
    low_stock_threshold: int = 3
    default_page_size: int = 12
    max_page_size: int = 100
    currency: str = "GEL"

    # --- Supabase Storage (არასავალდებულო — სურათებისთვის) --------------------
    supabase_project_ref: str = ""
    supabase_service_role_key: str = ""
    # Public on purpose: signed URLs expire, which would break storefront pages
    # and the image URLs snapshotted into past orders.
    supabase_storage_bucket: str = "product-images"

    # Business-day boundaries ("today", date filters) are computed here, not in
    # UTC - an order placed at 01:00 Tbilisi time belongs to that day, not to
    # the previous one.
    store_timezone: str = "Asia/Tbilisi"

    max_image_bytes: int = 5 * 1024 * 1024
    max_image_pixels: int = 50_000_000

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """URI-ს ისე ვიღებთ, როგორც Supabase-ის dashboard-ი გვაძლევს.

        ორი რამ უნდა შესწორდეს, თორემ კავშირი ჩავარდება და შეცდომა ბუნდოვანია:
        1. SQLAlchemy-ს async ძრავს `postgresql+asyncpg://` სქემა სჭირდება.
        2. `?sslmode=` libpq-ს პარამეტრია — asyncpg მას ვერ იგებს და TypeError-ს აგდებს.
           TLS-ს `session.py` connect_args-ით რთავს.
        """
        url = value.strip()
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        for junk in ("?sslmode=require", "&sslmode=require", "?sslmode=prefer", "&sslmode=prefer"):
            url = url.replace(junk, "")
        return url

    @property
    def cookie_path(self) -> str:
        """Where the browser should send the refresh cookie."""
        return self.refresh_cookie_path or f"{self.api_v1_prefix}/auth"

    @property
    def cookie_secure(self) -> bool:
        if self.refresh_cookie_secure is not None:
            return self.refresh_cookie_secure
        return self.app_env not in {"development", "test"}

    @property
    def refresh_cookie_max_age(self) -> int:
        """Seconds, matching the token's own lifetime in the database."""
        return self.refresh_token_ttl_days * 24 * 60 * 60

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    @property
    def requires_ssl(self) -> bool:
        """managed Postgres (Supabase) TLS-ს ითხოვს, ლოკალური კონტეინერი — არა."""
        return not any(host in self.database_url for host in ("localhost", "127.0.0.1"))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

__all__ = ["Settings", "get_settings", "settings"]
