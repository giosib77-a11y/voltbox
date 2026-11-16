"""frontend/render.yaml - promises of the storefront blueprint that Render will
not check. Does not import `app`."""

from pathlib import Path
from typing import Any

import yaml

BLUEPRINT = Path(__file__).resolve().parents[2] / "frontend" / "render.yaml"

# Markers of the temporary onrender.com values: the sitemap rewrite target, the
# connect-src address, and the HSTS max-age=300. They come off when voltbox.ge
# is bought; this count must then drop with them, never change by accident.
TEMP_ONRENDER_MARKERS = 3


def _storefront() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(BLUEPRINT.read_text(encoding="utf-8"))
    services: list[dict[str, Any]] = loaded["services"]
    (service,) = [s for s in services if s["name"] == "voltbox-storefront"]
    return service


def test_storefront_sends_a_short_hsts_on_every_path() -> None:
    """Exactly one rule, 300 s, no includeSubDomains and no preload: the site is
    on a temporary address and a mistake must stay cheap to undo."""
    rules = [h for h in _storefront()["headers"] if h["name"] == "Strict-Transport-Security"]
    assert len(rules) == 1
    assert rules[0]["path"] == "/*"
    assert rules[0]["value"] == "max-age=300"


def test_temp_onrender_markers_are_untouched() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")
    assert text.count("TEMP-ONRENDER") == TEMP_ONRENDER_MARKERS
