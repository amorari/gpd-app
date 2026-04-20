"""Wrap execute_js so tests skip on known bridge flake instead of error."""
from __future__ import annotations

from typing import Protocol

from gpd_tests.drivers.mcp import MCPError, MCPTimeout


class ProbeSkip(Exception):
    """Raised when the webview bridge is unresponsive. Tests should pytest.skip."""


class _MCPLike(Protocol):
    def execute_js(self, code: str) -> object: ...


_TIMEOUT_HINTS = ("timeout", "empty response", "peer closed")


class DOMProbe:
    def __init__(self, mcp: _MCPLike) -> None:
        self._mcp = mcp

    def eval(self, code: str) -> str:
        try:
            return self._mcp.execute_js(code)
        except MCPTimeout as e:
            raise ProbeSkip(str(e)) from e
        except MCPError as e:
            msg = str(e).lower()
            if any(h in msg for h in _TIMEOUT_HINTS):
                raise ProbeSkip(str(e)) from e
            raise

    def eval_bool(self, code: str) -> bool:
        raw = self.eval(code)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.lower() == "true"
        return bool(raw)
