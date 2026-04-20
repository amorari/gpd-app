"""Real OS-level input: cliclick for mouse, AppleScript for keys."""
from __future__ import annotations

import shutil
import subprocess


_KEY_CODES: dict[str, int] = {
    "escape": 53,
    "esc": 53,
    "return": 36,
    "enter": 36,
    "tab": 48,
    "space": 49,
    "delete": 51,
    "backspace": 51,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
}


class OSInputClient:
    def __init__(self) -> None:
        if not shutil.which("cliclick"):
            raise RuntimeError(
                "cliclick not on PATH. Install with: brew install cliclick"
            )

    def click(self, x: int, y: int) -> None:
        subprocess.run(
            ["cliclick", f"c:{x},{y}"],
            capture_output=True,
            text=True,
            check=True,
        )

    def move(self, x: int, y: int) -> None:
        subprocess.run(
            ["cliclick", f"m:{x},{y}"],
            capture_output=True,
            text=True,
            check=True,
        )

    def type_text(self, text: str) -> None:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{escaped}"'
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )

    def press_key(self, key: str) -> None:
        if key not in _KEY_CODES:
            raise ValueError(f"unknown key: {key}")
        code = _KEY_CODES[key]
        script = f'tell application "System Events" to key code {code}'
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
