"""Frontmost-app and bundle-ID helpers for GUI tests.

These wrappers centralize the macOS lsregister / osascript dance that used
to live inline in ``tests/flows/test_deep_link.py``. The goal is that any
test which sends synthetic keystrokes first asserts the GPD bundle owns
the keyboard focus — otherwise AppleScript fan-out can deliver a shortcut
to Finder, Terminal, or a stale release build installed in /Applications.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

_LSREGISTER = (
    "/System/Library/Frameworks/CoreServices.framework"
    "/Frameworks/LaunchServices.framework/Support/lsregister"
)

_GPD_BUNDLE_PREFIX = "inc.psi.gpd"
_DEFAULT_GPD_BUNDLE_ID = "inc.psi.gpd"


def schemes_registered_for_gpd() -> set[str] | None:
    """Query lsregister for URL schemes claimed by any GPD bundle.

    Returns a set of bundle IDs that claim 'gpd' as a URL scheme, or None
    if lsregister is unavailable or the output cannot be parsed.
    """
    lsr_path = Path(_LSREGISTER)
    if not lsr_path.exists():
        return None
    try:
        result = subprocess.run(
            [str(lsr_path), "-dump"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

    bundle_ids: set[str] = set()
    current_bundle: str | None = None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        # lsregister -dump groups entries; bundle id lines look like:
        #   bundle id:    inc.psi.gpd
        if stripped.startswith("bundle id:"):
            current_bundle = stripped.split(":", 1)[1].strip()
        # URL scheme lines look like:
        #   url schemes:  gpd
        elif stripped.startswith("url schemes:") and current_bundle:
            schemes_text = stripped.split(":", 1)[1].strip()
            schemes = [s.strip() for s in schemes_text.split(",")]
            if "gpd" in schemes:
                bundle_ids.add(current_bundle)
    # Return the set (possibly empty) so callers can distinguish "lsregister
    # available but nothing registered" from "lsregister unavailable" (None).
    return bundle_ids


def _resolve_gpd_bundle_id() -> str:
    """Pick the bundle id to activate.

    Priority:
    1. ``GPD_BUNDLE_ID`` env var (explicit override).
    2. ``GPD_APP_PATH`` env var — read ``Contents/Info.plist`` via
       ``CFBundleIdentifier``.
    3. Hardcoded default ``inc.psi.gpd``.
    """
    override = os.environ.get("GPD_BUNDLE_ID")
    if override:
        return override

    app_path = os.environ.get("GPD_APP_PATH")
    if app_path:
        plist = Path(app_path) / "Contents" / "Info.plist"
        if plist.exists():
            try:
                result = subprocess.run(
                    [
                        "/usr/libexec/PlistBuddy",
                        "-c",
                        "Print :CFBundleIdentifier",
                        str(plist),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                bundle = result.stdout.strip()
                if bundle:
                    return bundle
            except (subprocess.TimeoutExpired, OSError):
                pass

    return _DEFAULT_GPD_BUNDLE_ID


def gpd_is_frontmost() -> bool:
    """Return True iff the frontmost app's bundle id starts with ``inc.psi.gpd``.

    Uses osascript + System Events. Returns False on any osascript failure
    (timeout, Accessibility permission denied, non-zero exit).
    """
    script = (
        'tell application "System Events" to '
        "get bundle identifier of first application process "
        "whose frontmost is true"
    )
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    if result.returncode != 0:
        return False
    front = result.stdout.strip()
    return front.startswith(_GPD_BUNDLE_PREFIX)


def ensure_gpd_frontmost(timeout_s: float = 3.0) -> None:
    """Activate the GPD bundle and wait until it reports as frontmost.

    Raises ``RuntimeError`` if activation does not take effect within
    ``timeout_s`` seconds.
    """
    if gpd_is_frontmost():
        return

    bundle_id = _resolve_gpd_bundle_id()
    activate_script = f'tell application id "{bundle_id}" to activate'
    try:
        subprocess.run(
            ["/usr/bin/osascript", "-e", activate_script],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise RuntimeError(
            f"osascript activate failed for bundle {bundle_id!r}: {exc}"
        ) from exc

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if gpd_is_frontmost():
            return
        time.sleep(0.1)

    raise RuntimeError(
        f"GPD bundle {bundle_id!r} did not become frontmost within "
        f"{timeout_s:.1f}s"
    )


_MODIFIER_MAP = {
    "cmd": "command down",
    "command": "command down",
    "shift": "shift down",
    "option": "option down",
    "alt": "option down",
    "ctrl": "control down",
    "control": "control down",
}


def keystroke(char: str, modifiers: list[str] | None = None) -> None:
    """Send a keystroke to the GPD app, asserting frontmost first.

    ``modifiers`` accepts short names: ``cmd``/``command``, ``shift``,
    ``option``/``alt``, ``ctrl``/``control``.
    """
    ensure_gpd_frontmost()

    mods = modifiers or []
    applescript_mods = []
    for m in mods:
        key = m.strip().lower()
        if key not in _MODIFIER_MAP:
            raise ValueError(f"unknown modifier: {m!r}")
        applescript_mods.append(_MODIFIER_MAP[key])

    # Escape the character for AppleScript string literal.
    escaped = char.replace("\\", "\\\\").replace('"', '\\"')
    if applescript_mods:
        using = "{" + ", ".join(applescript_mods) + "}"
        script = (
            f'tell application "System Events" to '
            f'keystroke "{escaped}" using {using}'
        )
    else:
        script = (
            f'tell application "System Events" to keystroke "{escaped}"'
        )

    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise RuntimeError(f"osascript keystroke failed: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"osascript keystroke returned {result.returncode}: "
            f"{result.stderr.strip()}"
        )


__all__ = [
    "schemes_registered_for_gpd",
    "gpd_is_frontmost",
    "ensure_gpd_frontmost",
    "keystroke",
]
