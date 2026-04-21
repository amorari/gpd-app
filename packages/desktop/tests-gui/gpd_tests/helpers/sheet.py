"""Detect native macOS sheets (modal children of a window) without activating."""
from __future__ import annotations

from gpd_tests.drivers.ax import _osascript


def has_native_sheet(app_name: str = "GPD") -> bool:
    """Return True when the first window of `app_name` has at least one sheet."""
    script = (
        f'tell application "System Events" to tell process "{app_name}" '
        f'to return (count of sheets of window 1)'
    )
    try:
        raw = _osascript(script).strip()
    except Exception:
        return False
    return raw.isdigit() and int(raw) > 0
