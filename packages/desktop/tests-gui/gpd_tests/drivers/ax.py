"""macOS Accessibility driver via osascript/System Events."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


def _esc_as(s: str) -> str:
    """Escape a string for embedding inside an AppleScript double-quoted literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _osascript(script: str, *, timeout_s: float = 10.0) -> str:
    if not shutil.which("osascript"):
        raise RuntimeError("osascript not available")
    r = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if r.returncode != 0:
        raise RuntimeError(f"osascript failed: {r.stderr.strip()}")
    return r.stdout.strip()


def _default_app_name() -> str:
    """Derive the default AX process name from GPD_APP_PATH."""
    return Path(os.environ.get("GPD_APP_PATH", "/Applications/GPD.app")).stem


class AXClient:
    def __init__(self, app_name: str | None = None) -> None:
        self._app = app_name if app_name is not None else _default_app_name()

    def activate(self) -> None:
        _osascript(f'tell application "{_esc_as(self._app)}" to activate')

    def top_level_menus(self) -> list[str]:
        app = _esc_as(self._app)
        script = (
            'set AppleScript\'s text item delimiters to "|"\n'
            f'tell application "System Events" to tell process "{app}" '
            f'to return (name of every menu bar item of menu bar 1) as string'
        )
        raw = _osascript(script)
        if not raw:
            return []
        return [x.strip() for x in raw.split("|") if x.strip() and x.strip() != "Apple"]

    def menu_item_exists(self, menu: str, item: str) -> bool:
        # Menu-bar queries work without bringing GPD frontmost — only window
        # queries require activation.
        app = _esc_as(self._app)
        menu_e = _esc_as(menu)
        item_e = _esc_as(item)
        script = f'''
        tell application "System Events"
          tell process "{app}"
            try
              set _m to menu bar item "{menu_e}" of menu bar 1
              set _i to menu item "{item_e}" of menu 1 of _m
              return "true"
            on error
              return "false"
            end try
          end tell
        end tell
        '''
        return _osascript(script).strip() == "true"

    def menu_item_enabled(self, menu: str, item: str) -> bool:
        app = _esc_as(self._app)
        menu_e = _esc_as(menu)
        item_e = _esc_as(item)
        script = f'''
        tell application "System Events"
          tell process "{app}"
            try
              set _m to menu bar item "{menu_e}" of menu bar 1
              set _i to menu item "{item_e}" of menu 1 of _m
              return (enabled of _i) as string
            on error
              return "false"
            end try
          end tell
        end tell
        '''
        return _osascript(script).strip() == "true"

    def click_menu_item(self, menu: str, item: str) -> None:
        app = _esc_as(self._app)
        menu_e = _esc_as(menu)
        item_e = _esc_as(item)
        script = f'''
        tell application "System Events"
          tell process "{app}"
            click menu item "{item_e}" of menu 1 of menu bar item "{menu_e}" of menu bar 1
          end tell
        end tell
        '''
        _osascript(script)

    def items_of(self, menu: str) -> list[str]:
        """Return names of every menu item under the given top-level menu.

        AppleScript's `missing value` entries are filtered out — they
        represent separator items and are not useful as test targets.
        """
        raw = self._raw_items_of(menu)
        if raw is None:
            return []
        return [
            x.strip()
            for x in raw.split("|")
            if x.strip() and x.strip() != "missing value"
        ]

    def _raw_items_of(self, menu: str) -> str | None:
        """Return the raw `|`-joined AppleScript output, or None on failure.

        Separator entries remain as the literal "missing value" token so
        callers that need positional mapping against a sibling query (e.g.
        enabled_items_of) can zip across the unfiltered list.
        """
        app = _esc_as(self._app)
        menu_e = _esc_as(menu)
        script = (
            'set AppleScript\'s text item delimiters to "|"\n'
            f'tell application "System Events" to tell process "{app}" '
            f'to return (name of every menu item of menu 1 of menu bar item '
            f'"{menu_e}" of menu bar 1) as string'
        )
        try:
            raw = _osascript(script)
        except RuntimeError:
            return None
        return raw or None

    def enabled_items_of(self, menu: str) -> list[str]:
        """Return names of menu items that are currently enabled.

        Zips the raw (unfiltered) names against the enabled-flag list
        positionally, then drops separator pairs. Necessary because a
        separator between items would shift the enabled-flag alignment
        if we zipped against pre-filtered names.
        """
        raw_names = self._raw_items_of(menu)
        if raw_names is None:
            return []
        app = _esc_as(self._app)
        menu_e = _esc_as(menu)
        script = (
            'set AppleScript\'s text item delimiters to "|"\n'
            f'tell application "System Events" to tell process "{app}" '
            f'to return (enabled of every menu item of menu 1 of menu bar '
            f'item "{menu_e}" of menu bar 1) as string'
        )
        try:
            raw_flags = _osascript(script)
        except RuntimeError:
            return []
        names = [n.strip() for n in raw_names.split("|")]
        flags = [f.strip() for f in raw_flags.split("|")]
        return [
            n
            for n, f in zip(names, flags)
            if n and n != "missing value" and f == "true"
        ]

    def main_window(self) -> dict[str, Any]:
        """Return the main window geometry via AX: {x, y, w, h, title}.

        Returns the main window geometry via AX: {x, y, w, h, title}.
        """
        self.activate()
        app = _esc_as(self._app)
        for _ in range(20):
            probe = _osascript(
                f'tell application "System Events" to tell process "{app}" '
                f'to return count of windows'
            )
            if probe.strip().isdigit() and int(probe) >= 1:
                break
            time.sleep(0.1)
        # Use a delimiter that cannot appear in a window title.
        delim = "|||"
        script = f'''
        tell application "System Events"
          tell process "{app}"
            set _w to first window
            set _pos to position of _w
            set _sz to size of _w
            set _t to name of _w
            return (item 1 of _pos as string) & "{delim}" & (item 2 of _pos as string) & "{delim}" & (item 1 of _sz as string) & "{delim}" & (item 2 of _sz as string) & "{delim}" & _t
          end tell
        end tell
        '''
        raw = _osascript(script)
        parts = raw.split(delim)
        return {
            "x": int(parts[0]),
            "y": int(parts[1]),
            "w": int(parts[2]),
            "h": int(parts[3]),
            "title": delim.join(parts[4:]).strip(),
        }
