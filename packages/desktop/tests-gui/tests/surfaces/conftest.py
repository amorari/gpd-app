"""Fixtures shared by Phase 2 surface tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe
from gpd_tests.helpers.navigator import Navigator


@pytest.fixture
def nav(mcp) -> Navigator:
    return Navigator(mcp)


@pytest.fixture
def dom(mcp) -> DOMProbe:
    return DOMProbe(mcp)


@pytest.fixture
def gpd_key() -> str:
    """Return the GPD LiteLLM key; skip if auth.json is absent or has no gpd key.

    The key lives in ~/.local/share/opencode/auth.json (written by the GPD
    installer / onboarding flow). Tests marked @pytest.mark.real_backend
    depend on this. Non-real-backend tests must not request this fixture.
    """
    import json as _json
    xdg = os.environ.get("XDG_DATA_HOME")
    auth_path = (
        Path(xdg) / "opencode" / "auth.json"
        if xdg
        else Path.home() / ".local" / "share" / "opencode" / "auth.json"
    )
    try:
        data = _json.loads(auth_path.read_text())
        key = data.get("gpd", {}).get("key", "")
    except (FileNotFoundError, _json.JSONDecodeError):
        key = ""
    if not key:
        pytest.skip(
            f"GPD key not found in {auth_path}; skipping real-backend test"
        )
    return key