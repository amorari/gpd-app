"""MCP Unix-socket client for tauri-plugin-mcp.

Wire format: line-delimited JSON.
Request:  {"id": "<str>", "command": "<name>", "payload": <object>}\\n
Response: {"success": bool, "data": any, "error": str|null, "id": "<str>"}\\n

Notes (discovered 2026-04-20):
- `id` MUST be a string. Integer ids are rejected.
- `payload` MUST be present on every request (use `{}` if empty).
- Some commands require an auth token; we don't set one here — tests that need
  auth-gated commands must inject a token via `MCPClient(auth_token=...)`.
"""
from __future__ import annotations

import glob
import json
import os
import platform
import socket
import uuid
from typing import Any


def _discover_socket_path() -> str:
    """Resolve the MCP socket path at call time.

    macOS-only: searches under /var/folders/*/*/T/ for tauri-mcp.sock.
    Order: GPD_MCP_SOCKET env override > search under /var/folders/*/*/T/.
    Raises FileNotFoundError if no socket exists yet (caller should retry
    after launching GPD rather than connecting to a stale default).
    Raises RuntimeError on non-macOS platforms.
    """
    if platform.system() != "Darwin":
        raise RuntimeError("MCP socket discovery is macOS-only")
    env = os.environ.get("GPD_MCP_SOCKET")
    if env:
        return env
    matches = glob.glob("/var/folders/*/*/T/tauri-mcp.sock")
    if matches:
        return matches[0]
    raise FileNotFoundError(
        "tauri-mcp.sock not found; launch GPD before constructing MCPClient"
    )


class MCPError(RuntimeError):
    """Raised when an MCP command returns success=False."""


class MCPTimeout(RuntimeError):
    """Raised when the socket does not respond within the deadline."""


class MCPClient:
    def __init__(
        self,
        socket_path: str | None = None,
        *,
        timeout_s: float = 10.0,
        auth_token: str | None = None,
    ) -> None:
        self._path = socket_path if socket_path is not None else _discover_socket_path()
        self._timeout = timeout_s
        self._auth = auth_token

    def _call(self, command: str, payload: dict[str, Any] | None = None) -> Any:
        req = {
            "id": str(uuid.uuid4()),
            "command": command,
            "payload": {} if payload is None else payload,
        }
        if self._auth:
            req["authToken"] = self._auth
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self._timeout)
        try:
            sock.connect(self._path)
            sock.sendall((json.dumps(req) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
        except socket.timeout as e:
            raise MCPTimeout(f"timeout on {command}") from e
        finally:
            sock.close()
        line, _, _ = buf.partition(b"\n")
        if not line.strip():
            raise MCPTimeout(
                f"empty response on {command} (peer closed socket)"
            )
        resp = json.loads(line.decode())
        if not resp.get("success", False):
            raise MCPError(resp.get("error") or "unknown error")
        return resp.get("data")

    def ping(self) -> None:
        self._call("ping")

    def list_windows(self) -> list[dict[str, Any]]:
        data = self._call("list_windows")
        if isinstance(data, dict) and "windows" in data:
            return list(data["windows"] or [])
        return list(data or [])

    def take_screenshot(self, *, window_label: str = "main") -> str:
        """Return the screenshot as a data URI."""
        data = self._call("take_screenshot", {"windowLabel": window_label})
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        raise MCPError(f"unexpected screenshot response: {data!r}")

    def take_screenshot_bytes(self, *, window_label: str = "main") -> bytes:
        """Decode and return the screenshot as JPEG bytes."""
        import base64

        data_uri = self.take_screenshot(window_label=window_label)
        _, _, b64 = data_uri.partition(",")
        return base64.b64decode(b64)

    def reload(self) -> None:
        self._call("navigate_webview", {"action": "reload", "windowLabel": "main"})

    def navigate(self, url: str, *, window_label: str = "main") -> None:
        """Drive the webview to `url`. Uses navigate_webview.navigate."""
        self._call(
            "navigate_webview",
            {"action": "navigate", "url": url, "windowLabel": window_label},
        )

    def current_url(self, *, window_label: str = "main") -> str:
        """Return the webview's current URL."""
        data = self._call(
            "navigate_webview",
            {"action": "get_url", "windowLabel": window_label},
        )
        if isinstance(data, dict) and "url" in data:
            return data["url"]
        raise MCPError(f"unexpected get_url response: {data!r}")

    def execute_js(self, code: str, *, window_label: str = "main") -> str:
        """Evaluate JS in the webview. Returns the stringified result.

        May raise MCPError with "Timeout..." if the webview-side bridge is
        unresponsive — callers should treat that as a non-fatal signal and
        fall back to other drive paths.
        """
        data = self._call(
            "execute_js", {"code": code, "windowLabel": window_label}
        )
        # The vendored tauri-plugin-mcp guest-js wraps results as
        # {result: <stringified value>, type: <typeof>}. Unwrap so callers
        # see the stringified value directly (matches the pre-vendor shape).
        if isinstance(data, dict) and "result" in data:
            return data["result"]
        return data

    def restart_app(self) -> None:
        """WARNING: triggers a full app restart. Callers must own the lifecycle."""
        self._call("restart_app")
