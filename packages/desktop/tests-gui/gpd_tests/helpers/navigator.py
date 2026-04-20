"""Drive GPD route changes via MCP navigate + URL polling."""
from __future__ import annotations

import base64
import time
from typing import Protocol


BASE = "tauri://localhost"


def encode_dir_token(path: str) -> str:
    """Route token for `/:dir`: base64url of the filesystem path, no padding."""
    return base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")


def route_home() -> str:
    return f"{BASE}/"


def route_loading() -> str:
    return f"{BASE}/loading"


def route_project(path: str) -> str:
    return f"{BASE}/{encode_dir_token(path)}"


def route_session(session_id: str | None = None) -> str:
    if session_id is None:
        return f"{BASE}/session"
    return f"{BASE}/session/{session_id}"


class _MCPLike(Protocol):
    def navigate(self, url: str) -> None: ...
    def current_url(self) -> str: ...


class Navigator:
    def __init__(self, mcp: _MCPLike) -> None:
        self._mcp = mcp

    def go(self, url: str, *, timeout_s: float = 5.0, poll_s: float = 0.1) -> None:
        """Navigate and wait for current_url to match."""
        self._mcp.navigate(url)
        deadline = time.monotonic() + timeout_s
        last = ""
        while time.monotonic() < deadline:
            try:
                last = self._mcp.current_url()
            except Exception:
                last = ""
            if last == url:
                return
            time.sleep(poll_s)
        raise TimeoutError(
            f"navigate to {url} did not take effect; current={last!r}"
        )
