"""Detect native macOS sheets (modal children of a window) without activating."""
from __future__ import annotations

from gpd_tests.drivers.ax import _default_app_name, _esc_as, _osascript


def has_native_sheet(app_name: str | None = None) -> bool:
    """Return True when the first window of `app_name` has at least one sheet.

    If ``app_name`` is None, derives the AX process name from GPD_APP_PATH
    (same as AXClient) so dev builds (GPD-Dev.app, GPD-nightly.app, etc.)
    resolve to the right AX process instead of hard-coding "GPD".
    """
    app = _esc_as(app_name if app_name is not None else _default_app_name())
    script = (
        f'tell application "System Events" to tell process "{app}" '
        f'to return (count of sheets of window 1)'
    )
    try:
        raw = _osascript(script).strip()
    except RuntimeError:
        # _osascript raises RuntimeError on non-zero exit (process missing,
        # accessibility permission denied, window 1 not present). Treat
        # those as "no sheet" and let the caller decide. Other exceptions
        # (bugs in the helper, import errors) propagate.
        return False
    return raw.isdigit() and int(raw) > 0
