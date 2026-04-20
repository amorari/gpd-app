"""Shared helper: derive the macOS bundle ID from the running GPD app.

Import this module from reset.py and discover_mcp_token.py rather than
duplicating the logic.
"""
from __future__ import annotations

import os
from pathlib import Path

_APP_NAME_TO_BUNDLE_ID: dict[str, str] = {
    "GPD": "inc.psi.gpd",
    "GPD Dev": "inc.psi.gpd.dev",
    "GPD Beta": "inc.psi.gpd.beta",
}


def app_name() -> str:
    """Derive the macOS application name from GPD_APP_PATH.

    Returns "GPD Dev" for a debug bundle, "GPD Beta" for a beta build,
    and "GPD" for the release bundle. Tauri names the binary inside
    Contents/MacOS/ identically to the .app stem.
    """
    app_path = os.environ.get("GPD_APP_PATH", "/Applications/GPD.app")
    return Path(app_path).stem


def bundle_id() -> str:
    """Return the macOS bundle ID for the current GPD variant.

    Falls back to "inc.psi.gpd" for unknown app names.
    """
    name = app_name()
    return _APP_NAME_TO_BUNDLE_ID.get(name, "inc.psi.gpd")
