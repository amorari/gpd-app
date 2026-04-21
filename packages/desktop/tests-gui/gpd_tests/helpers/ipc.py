"""Invoke a Tauri command via MCP execute_js.

Tauri exposes `window.__TAURI_INTERNALS__.invoke(cmd, args)` which returns a
Promise. We wrap it in an async IIFE and return the JSON-serialized result.
Errors thrown by the command land in the Promise rejection path; we catch and
re-serialize as {"__tauri_error__": message} so execute_js doesn't timeout.
"""
from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable


class IPCError(RuntimeError):
    """A Tauri command returned an error or threw an exception."""


@runtime_checkable
class _MCPLike(Protocol):
    def execute_js(self, js: str, window_label: str = "main") -> str: ...


def invoke_via_mcp(
    mcp: _MCPLike,
    command: str,
    args: dict[str, Any] | None = None,
    *,
    window_label: str = "main",
) -> Any:
    args_json = json.dumps(args or {})
    cmd_json = json.dumps(command)
    js = f"""
(async () => {{
  try {{
    const r = await window.__TAURI_INTERNALS__.invoke({cmd_json}, {args_json});
    return JSON.stringify(r === undefined ? null : r);
  }} catch (e) {{
    return JSON.stringify({{ __tauri_error__: String(e && e.message ? e.message : e) }});
  }}
}})()
"""
    raw = mcp.execute_js(js, window_label=window_label)
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        raise IPCError(f"non-JSON response from {command!r}: {raw!r}") from e

    if isinstance(parsed, dict) and "__tauri_error__" in parsed:
        raise IPCError(parsed["__tauri_error__"])
    return parsed
