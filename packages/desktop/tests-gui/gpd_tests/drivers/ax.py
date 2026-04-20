"""macOS Accessibility driver via osascript/System Events."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


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


@dataclass(frozen=True)
class MenuItem:
    menu: str
    name: str


class AXClient:
    def __init__(self, app_name: str = "GPD") -> None:
        self._app = app_name

    def activate(self) -> None:
        _osascript(f'tell application "{self._app}" to activate')

    def top_level_menus(self) -> list[str]:
        script = (
            'set AppleScript\'s text item delimiters to "|"\n'
            f'tell application "System Events" to tell process "{self._app}" '
            f'to return (name of every menu bar item of menu bar 1) as string'
        )
        raw = _osascript(script)
        if not raw:
            return []
        return [x.strip() for x in raw.split("|") if x.strip() and x.strip() != "Apple"]

    def menu_item_exists(self, menu: str, item: str) -> bool:
        # Menu-bar queries work without bringing GPD frontmost — only window
        # queries require activation.
        script = f'''
        tell application "System Events"
          tell process "{self._app}"
            try
              set _m to menu bar item "{menu}" of menu bar 1
              set _i to menu item "{item}" of menu 1 of _m
              return "true"
            on error
              return "false"
            end try
          end tell
        end tell
        '''
        return _osascript(script).strip() == "true"

    def menu_item_enabled(self, menu: str, item: str) -> bool:
        script = f'''
        tell application "System Events"
          tell process "{self._app}"
            try
              set _m to menu bar item "{menu}" of menu bar 1
              set _i to menu item "{item}" of menu 1 of _m
              return (enabled of _i) as string
            on error
              return "false"
            end try
          end tell
        end tell
        '''
        return _osascript(script).strip() == "true"

    def click_menu_item(self, menu: str, item: str) -> None:
        script = f'''
        tell application "System Events"
          tell process "{self._app}"
            click menu item "{item}" of menu 1 of menu bar item "{menu}" of menu bar 1
          end tell
        end tell
        '''
        _osascript(script)

    def items_of(self, menu: str) -> list[str]:
        """Return names of every menu item under the given top-level menu.

        AppleScript's `missing value` entries are filtered out — they
        represent separator items and are not useful as test targets.
        """
        script = (
            'set AppleScript\'s text item delimiters to "|"\n'
            f'tell application "System Events" to tell process "{self._app}" '
            f'to return (name of every menu item of menu 1 of menu bar item '
            f'"{menu}" of menu bar 1) as string'
        )
        try:
            raw = _osascript(script)
        except RuntimeError:
            return []
        if not raw:
            return []
        return [
            x.strip()
            for x in raw.split("|")
            if x.strip() and x.strip() != "missing value"
        ]

    def enabled_items_of(self, menu: str) -> list[str]:
        """Return names of menu items that are currently enabled."""
        names = self.items_of(menu)
        if not names:
            return []
        script = (
            'set AppleScript\'s text item delimiters to "|"\n'
            f'tell application "System Events" to tell process "{self._app}" '
            f'to return (enabled of every menu item of menu 1 of menu bar '
            f'item "{menu}" of menu bar 1) as string'
        )
        try:
            raw = _osascript(script)
        except RuntimeError:
            return []
        flags = [f.strip() for f in raw.split("|")]
        # flags length may differ from names if AppleScript emits extra
        # entries for separators; zip truncates to the shorter sequence.
        return [name for name, flag in zip(names, flags) if flag == "true"]

    def main_window(self) -> dict[str, Any]:
        """Return the main window geometry via AX: {x, y, w, h, title}.

        WARNING: AX window queries require GPD to be frontmost and this call
        WILL activate GPD, stealing focus from the current app. Prefer
        MCPClient.list_windows() when you only need geometry/title — it
        returns the same data without activation.
        """
        self.activate()
        import time

        for _ in range(20):
            probe = _osascript(
                f'tell application "System Events" to tell process "{self._app}" '
                f'to return count of windows'
            )
            if probe.strip().isdigit() and int(probe) >= 1:
                break
            time.sleep(0.1)
        # Use a delimiter that cannot appear in a window title.
        delim = "|||"
        script = f'''
        tell application "System Events"
          tell process "{self._app}"
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
