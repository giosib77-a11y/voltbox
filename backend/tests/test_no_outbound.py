"""A test run reaches no service outside this machine.

conftest blanks every outbound credential in the environment, and an
environment variable beats `.env`. The first test builds Settings from an
`.env` that holds a live-looking value for every secret, as a developer's
does, and checks that none survives. It lists Settings' SecretStr fields
rather than naming them, so a credential added later fails here until
conftest blanks it too. It does not depend on what the developer's own `.env`
holds, so it fails the same way on every machine.
"""

from pathlib import Path

from app.core.config import Settings, settings
from pydantic import SecretStr

#: Secrets that reach nothing outside: the JWT key only signs, and conftest
#: points the database at the local test database (checked below).
LOCAL_SECRETS = {"jwt_secret", "database_url"}

LIVE = "live-0123456789abcdef0123456789abcdef"


def _outbound_credentials() -> list[str]:
    secrets = [n for n, f in Settings.model_fields.items() if f.annotation is SecretStr]
    return [name for name in secrets if name not in LOCAL_SECRETS]


def _leaked(loaded: Settings) -> list[str]:
    return [name for name in _outbound_credentials() if getattr(loaded, name).get_secret_value()]


def test_a_developers_env_file_leaves_no_credential_to_a_test(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    lines = [
        f"{name.upper()}={LIVE}"
        for name, field in Settings.model_fields.items()
        if field.annotation is SecretStr
    ]
    # The plain halves, so that "enabled" would be true if a secret got through.
    lines += ["TELEGRAM_CHAT_ID=-1001234567890", "EMAIL_FROM=VoltBox <orders@voltbox.ge>"]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    loaded = Settings(_env_file=env_file)

    assert _leaked(loaded) == []
    assert not loaded.telegram_enabled
    assert not loaded.order_email_enabled
    assert LIVE not in loaded.database_url.get_secret_value()
    # Not vacuous: the file was read, and a value the environment does not
    # override came through.
    assert loaded.telegram_chat_id == "-1001234567890"


def test_the_running_settings_hold_no_credential() -> None:
    """What this process actually loaded, from the developer's real `.env`."""
    assert _leaked(settings) == []
    assert not settings.telegram_enabled
    assert not settings.order_email_enabled


def test_the_list_covers_the_credentials_known_today() -> None:
    """Guards the enumeration: a type change would make the tests above pass empty."""
    assert set(_outbound_credentials()) >= {
        "telegram_bot_token",
        "resend_api_key",
        "supabase_service_role_key",
        "redis_url",
    }
