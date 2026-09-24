"""backend/render.yaml - what the file promises that Render will not check.

Render's JSON schema catches a misspelt key or a region that does not exist.
It does not know which path on this API survives a database outage, that it
accepts `sync: false` in an environment group and then ignores it, or which of
these variables are secrets. Those are the four promises below.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml
from app.core.config import Settings
from pydantic import SecretStr

from tests.test_rate_limit import load_gunicorn_conf

BLUEPRINT = Path(__file__).resolve().parents[1] / "render.yaml"


def _blueprint() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(BLUEPRINT.read_text(encoding="utf-8"))
    return loaded


def _service(kind: str) -> dict[str, Any]:
    services: list[dict[str, Any]] = _blueprint()["services"]
    (service,) = [s for s in services if s["type"] == kind]
    return service


def test_render_probes_liveness_not_the_database() -> None:
    """/api/v1/health answers 503 when the database is down, and Render restarts
    an instance that fails its check: a Supabase outage would become a restart
    loop, and a good deploy made during it would be cancelled."""
    assert _service("web")["healthCheckPath"] == "/api/v1/health/live"


def test_no_group_variable_waits_for_a_prompt() -> None:
    """Render's docs: `sync: false` in an environment group is ignored. The
    schema allows it, so without this a DATABASE_URL declared there would
    validate, sync, and never exist."""
    for group in _blueprint().get("envVarGroups", []):
        prompted = [v["key"] for v in group["envVars"] if "sync" in v]
        assert not prompted, f"{group['name']}: {prompted}"


def test_no_secret_is_written_into_the_file() -> None:
    """Secret by what it grants, which config.py records as SecretStr - not by
    what the variable is called."""
    secrets = {
        name.upper()
        for name, field in Settings.model_fields.items()
        if field.annotation is SecretStr
    }
    assert {"DATABASE_URL", "JWT_SECRET", "REDIS_URL"} <= secrets

    blueprint = _blueprint()
    variables = [v for s in blueprint["services"] for v in s.get("envVars", [])]
    variables += [v for g in blueprint.get("envVarGroups", []) for v in g["envVars"]]
    written = [v["key"] for v in variables if v.get("key") in secrets and "value" in v]

    assert not written


def test_the_api_s_values_pass_its_startup_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """What the file writes down, gunicorn.conf.py accepts - so a SITE_URL or an
    origin edited here into something it refuses fails in CI, not in a deploy.
    What Render prompts for is filled with a stand-in of the right shape."""
    for variable in _service("web")["envVars"]:
        if "value" in variable:
            monkeypatch.setenv(variable["key"], str(variable["value"]))
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.1.0.2")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    for key in (
        "ALLOW_NON_PRODUCTION_SERVER",
        "WEB_CONCURRENCY",
        "DB_POOL_SIZE",
        "DB_MAX_OVERFLOW",
        "DB_CONNECTION_BUDGET",
    ):
        monkeypatch.delenv(key, raising=False)

    load_gunicorn_conf().on_starting(None)
