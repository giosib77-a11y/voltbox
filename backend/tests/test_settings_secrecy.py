"""Printing settings shows no credential.

In 1a9d374 an AttributeError put the repr of `settings` into a session
transcript, and the service role key and the JWT secret were in it. A repr is
not a log line, so test_log_secrecy.py had no way to see it: nothing formats or
scrubs a repr on its way to a traceback, a debugger or a pytest failure. What
keeps the values out is their type, SecretStr, and that is what this file pins.
"""

from collections.abc import Callable
from typing import Any

import pytest
from app.core.config import Settings
from pydantic import ValidationError

DB_PASSWORD = "db-pw-7f3a91c2e8"
REDIS_PASSWORD = "redis-pw-5be04d18a6"
JWT_SECRET = "jwt-3b9e1c7a5f2d4e6b8a0c9d1e3f5a7b9c"
SERVICE_ROLE_KEY = "srk-8c1e6f0a2d4b9e7c"
TELEGRAM_TOKEN = "7412345678:AAH-tg-4d2a9f6c1e8b3a7d"
RESEND_KEY = "re_rs-9e2c4a7f1b3d"

#: Field -> the part of its value that must not be printed. For the URLs that
#: is the password inside them.
SECRETS = {
    "database_url": DB_PASSWORD,
    "jwt_secret": JWT_SECRET,
    "redis_url": REDIS_PASSWORD,
    "supabase_service_role_key": SERVICE_ROLE_KEY,
    "telegram_bot_token": TELEGRAM_TOKEN,
    "resend_api_key": RESEND_KEY,
}


def _settings(**overrides: Any) -> Settings:
    """Settings with known values, and without the developer's `.env`, which
    holds real ones."""
    values: dict[str, Any] = {
        "database_url": f"postgresql://postgres:{DB_PASSWORD}@db.example.supabase.co:5432/postgres",
        "jwt_secret": JWT_SECRET,
        "redis_url": f"rediss://default:{REDIS_PASSWORD}@redis.example:6379",
        "supabase_service_role_key": SERVICE_ROLE_KEY,
        "telegram_bot_token": TELEGRAM_TOKEN,
        "resend_api_key": RESEND_KEY,
    }
    return Settings(_env_file=None, **(values | overrides))


@pytest.mark.parametrize("show", [repr, str])
def test_printing_settings_shows_none_of_the_values(show: Callable[[object], str]) -> None:
    settings = _settings()

    printed = show(settings)

    assert [field for field, value in SECRETS.items() if value in printed] == []
    # Not vacuous: every value is there, only not printed.
    for field, value in SECRETS.items():
        assert value in getattr(settings, field).get_secret_value(), field


def test_a_value_that_fails_validation_is_not_quoted() -> None:
    """A value that fails validation never becomes a SecretStr, and pydantic
    quotes raw input in its errors. A JWT_SECRET one character short is the
    likeliest way there, and it is still the secret."""
    almost = JWT_SECRET[:31]

    with pytest.raises(ValidationError) as caught:
        _settings(jwt_secret=almost)

    assert almost not in str(caught.value)
    assert "jwt_secret" in str(caught.value), "the error still names the field"
