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


def _auto_detect_app_path() -> str:
    """Return the GPD app bundle path from env or in-tree build detection.

    Order: GPD_APP_PATH env → /Applications/GPD.app (installed) →
    in-tree debug build → in-tree release build → fall back to /Applications.
    """
    env = os.environ.get("GPD_APP_PATH")
    if env:
        return env
    prod = "/Applications/GPD.app"
    if os.path.exists(prod):
        return prod
    # Walk up from this file to find the Tauri bundle directories.
    # scripts/_bundle.py is at packages/desktop/tests-gui/scripts/_bundle.py
    # parents[0]=scripts/  parents[1]=tests-gui/  parents[2]=desktop/
    here = Path(__file__).resolve()
    desktop = here.parents[2]
    bundle_base = desktop / "src-tauri" / "target"
    for variant, name in [("debug", "GPD Dev.app"), ("release", "GPD.app")]:
        candidate = bundle_base / variant / "bundle" / "macos" / name
        if candidate.exists():
            return str(candidate)
    return prod


def app_name() -> str:
    """Derive the macOS application name from GPD_APP_PATH.

    Returns "GPD Dev" for a debug bundle, "GPD Beta" for a beta build,
    and "GPD" for the release bundle. Tauri names the binary inside
    Contents/MacOS/ identically to the .app stem.
    """
    return Path(_auto_detect_app_path()).stem


def bundle_id() -> str:
    """Return the macOS bundle ID for the current GPD variant.

    Falls back to "inc.psi.gpd" for unknown app names.
    """
    name = app_name()
    return _APP_NAME_TO_BUNDLE_ID.get(name, "inc.psi.gpd")
