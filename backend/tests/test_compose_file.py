"""backend/docker-compose.yml - the `api` service must not carry real credentials.

`backend/.env` normally points at the live Supabase project. An `env_file: .env`
on the `api` service (profile `full`) put every variable in it into the
container, so a local API would upload to the live bucket and send real Telegram
messages and email (A-063). The service now gets only explicit local values.
"""

from pathlib import Path
from typing import Any

import yaml
from app.core.config import Settings
from pydantic import SecretStr

COMPOSE_FILE = Path(__file__).resolve().parents[1] / "docker-compose.yml"

#: Secrets the local stack legitimately has: the compose database, the compose
#: Redis and a stand-in signing key. Every other SecretStr in Settings grants
#: access to something outside the machine.
LOCAL_SECRETS = {"DATABASE_URL", "JWT_SECRET", "REDIS_URL"}

#: Not secrets, but each one names an outside account or address, and the
#: feature that reads it is switched on by it (see Settings.telegram_enabled and
#: order_email_enabled).
EXTERNAL_PLAIN_SETTINGS = {"SUPABASE_PROJECT_REF", "TELEGRAM_CHAT_ID", "EMAIL_FROM"}


def _compose() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    return loaded


def _api_environment() -> dict[str, str]:
    environment: dict[str, str] = _compose()["services"]["api"]["environment"]
    return environment


def _external_settings() -> set[str]:
    secrets = {
        name.upper()
        for name, field in Settings.model_fields.items()
        if field.annotation is SecretStr
    }
    # Guards the derivation: if SecretStr stopped being how config.py marks
    # these, the set below would silently shrink.
    assert {"SUPABASE_SERVICE_ROLE_KEY", "TELEGRAM_BOT_TOKEN", "RESEND_API_KEY"} <= secrets
    return (secrets - LOCAL_SECRETS) | EXTERNAL_PLAIN_SETTINGS


def test_no_service_loads_an_env_file() -> None:
    """`.env` stays out of every container - `api` is the one that had it."""
    with_env_file = [name for name, spec in _compose()["services"].items() if "env_file" in spec]
    assert not with_env_file


def test_the_api_names_every_external_credential_and_leaves_it_empty() -> None:
    """Absent would be `.env`'s to fill if someone adds `env_file` back, or a
    default's to fill if one is added to Settings; present and empty is what
    keeps the outside services off. Storage, Telegram and email are all
    switched on by a non-empty value."""
    environment = _api_environment()
    external = _external_settings()

    missing = sorted(external - environment.keys())
    assert not missing, f"not set in the api service: {missing}"

    filled = sorted(name for name in external if str(environment[name]).strip())
    assert not filled, f"not empty in the api service: {filled}"


def test_the_api_environment_boots_settings_with_nothing_outbound() -> None:
    """The values written in the file are the whole configuration: Settings
    accepts them (the JWT secret is long enough, the empty strings are not a
    validation error) and every outside feature reads as off."""
    environment = {name.lower(): value for name, value in _api_environment().items()}
    # Only keys Settings knows - APP_ENV and DATABASE_URL are fields too, while
    # ALLOW_NON_PRODUCTION_SERVER is gunicorn.conf.py's and Settings ignores it.
    settings = Settings.model_validate(environment)

    assert settings.app_env == "development"
    assert settings.telegram_enabled is False
    assert settings.order_email_enabled is False
    assert settings.supabase_project_ref == ""
    assert settings.supabase_service_role_key.get_secret_value() == ""
    assert settings.db_ssl_mode == "disable"
    assert len(settings.jwt_secret.get_secret_value()) >= 32


def test_the_api_reaches_the_compose_database_and_redis_not_a_remote_one() -> None:
    environment = _api_environment()
    assert environment["DATABASE_URL"].endswith("@db:5432/voltbox")
    assert environment["REDIS_URL"] == "redis://redis:6379/0"
