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
        if not shutil.which("osascript"):
            raise RuntimeError("osascript not on PATH — required for keyboard input")

    def click(self, x: int, y: int) -> None:
        cmd = ["cliclick", f"c:{x},{y}"]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{cmd!r} timed out after 10s") from None
        except subprocess.CalledProcessError as e:
            raise subprocess.CalledProcessError(
                e.returncode, e.cmd, e.output,
                stderr=e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr,
            ) from e

    def move(self, x: int, y: int) -> None:
        cmd = ["cliclick", f"m:{x},{y}"]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{cmd!r} timed out after 10s") from None
        except subprocess.CalledProcessError as e:
            raise subprocess.CalledProcessError(
                e.returncode, e.cmd, e.output,
                stderr=e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr,
            ) from e

    def type_text(self, text: str) -> None:
        if "\n" in text or "\r" in text:
            raise ValueError(
                "type_text does not support newline characters; "
                "use press_key('return') or press_key('enter') instead"
            )
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{escaped}"'
        cmd = ["osascript", "-e", script]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{cmd!r} timed out after 10s") from None
        except subprocess.CalledProcessError as e:
            raise subprocess.CalledProcessError(
                e.returncode, e.cmd, e.output,
                stderr=e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr,
            ) from e

    def press_key(self, key: str) -> None:
        if key not in _KEY_CODES:
            raise ValueError(f"unknown key: {key}")
        code = _KEY_CODES[key]
        script = f'tell application "System Events" to key code {code}'
        cmd = ["osascript", "-e", script]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{cmd!r} timed out after 10s") from None
        except subprocess.CalledProcessError as e:
            raise subprocess.CalledProcessError(
                e.returncode, e.cmd, e.output,
                stderr=e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr,
            ) from e
