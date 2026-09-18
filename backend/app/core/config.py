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

    # --- brute force ----------------------------------------------------------
    # The rate limit on /auth/login counts per IP, and an attacker renting a
    # thousand of those gets a thousand times the allowance against one account.
    # These count on the account instead, which every attempt has in common.
    #
    # Ten is far more than a person mistypes and few enough that guessing is
    # hopeless: 10 per 15 minutes is under a thousand tries a day.
    #
    # The cost is that someone who knows an email can keep that account locked
    # by failing on purpose. It is bounded - the lock expires on its own, an
    # existing session keeps working because refresh does not go through here -
    # and the alternative is leaving a botnet unlimited attempts.
    max_failed_logins: int = 10
    login_lock_minutes: int = 15

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

    #: Where the shop lives, as a visitor types it. Every URL in the sitemap is
    #: built from this, so a wrong value publishes a map of pages that do not
    #: exist. No trailing slash.
    site_url: str = "http://localhost:5173"

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

    # What one upload may cost to decode - not what the file may weigh.
    #
    # `shrink_to_fit` decodes the whole bitmap, and what that costs is a property
    # of the format: measured on Pillow 12.3, 6.5 bytes per pixel for a phone's
    # JPEG against 15.8 for a WebP. A single pixel limit would therefore be
    # either unsafe for a WebP or useless for a photo, so the limit is memory and
    # storage.py turns it into a pixel limit per decode path (DECODE_COST).
    #
    # The ceiling for the process is WEB_CONCURRENCY x this, because the decode
    # runs synchronously on the event loop and a worker therefore decodes one
    # image at a time. The default is sized for a 512 MB container: 2 x 100 MiB
    # on top of two workers holding ~100 MB each at rest. It admits a 13.3
    # megapixel JPEG, which covers every phone's default photo.
    # docs/deployment.md has the value for a larger instance.
    max_image_decode_bytes: int = 100 * 1024 * 1024

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
    def is_deployed(self) -> bool:
        """Reachable from the internet, whichever of the two it calls itself.

        Staging is a deployment with a public address; the only thing it does
        not have is real customers. Anything hidden in production for being
        reachable has to be hidden there too - `gunicorn.conf.py` already
        treats the pair the same way.
        """
        return self.app_env in {"production", "staging"}

    @property
    def cors_origin_list(self) -> list[str]:
        """The origins in the form a browser sends them.

        An Origin header never ends in `/`, and CORSMiddleware compares exactly,
        so `https://voltbox.ge/` - the shape a copied URL has - allowed no one.
        That slash is dropped. Only after a scheme, so that `*/` is not turned
        into the wildcard; anything longer than a bare slash is left as written
        and still matches nothing.
        """
        origins = (o.strip() for o in self.cors_origins.split(","))
        return [o.removesuffix("/") if "://" in o else o for o in origins if o]

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
