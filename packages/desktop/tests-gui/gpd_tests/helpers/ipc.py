"""Invoke a Tauri command via MCP execute_js.

## Why this is not a simple `await` wrapper

`window.__TAURI_INTERNALS__.invoke(cmd, args)` returns a Promise. The obvious
implementation is an async IIFE: `(async () => await invoke(...))()`. That
doesn't work through our MCP bridge — the vendored `tauri-plugin-mcp` guest-js
evaluates the submitted code with `new Function('return (code)')()` and
immediately stringifies the result. The return value is a pending Promise
(`typeof === "object"`), `JSON.stringify(promise)` yields `"{}"`, and every
command appears to return an empty dict regardless of what it actually resolved
to.

Fix: submit the invocation as a *statement* that stashes the resolved value on
a unique `window.__gpd_ipc_slot_<n>` slot, then poll that slot via a separate
`execute_js` call until it reports completion. Once resolved, read + clear the
slot and return.
"""
from __future__ import annotations

import itertools
import json
import time
from typing import Any, Protocol, runtime_checkable


class IPCError(RuntimeError):
    """A Tauri command returned an error or threw an exception."""


@runtime_checkable
class _MCPLike(Protocol):
    def execute_js(self, js: str, window_label: str = "main") -> str: ...


_SLOT_COUNTER = itertools.count()


def invoke_via_mcp(
    mcp: _MCPLike,
    command: str,
    args: dict[str, Any] | None = None,
    *,
    window_label: str = "main",
    deadline_s: float = 20.0,
    poll_interval_s: float = 0.1,
) -> Any:
    args_json = json.dumps(args or {})
    cmd_json = json.dumps(command)
    slot = f"__gpd_ipc_slot_{next(_SLOT_COUNTER)}_{int(time.time() * 1000)}"

    # Step 1: submit. Must be a *statement* — no implicit return, no async
    # expression — so the MCP bridge doesn't see a Promise as the statement's
    # value. The async-IIFE writes its result to `window[slot]` when done.
    submit_js = (
        f"(function(){{"
        f"window[{json.dumps(slot)}]=null;"
        f"(async()=>{{"
        f"try{{"
        f"const r=await window.__TAURI_INTERNALS__.invoke({cmd_json},{args_json});"
        f"window[{json.dumps(slot)}]={{ok:true,value:r===undefined?null:r}};"
        f"}}catch(e){{"
        f"window[{json.dumps(slot)}]={{ok:false,err:String(e&&e.message?e.message:e)}};"
        f"}}"
        f"}})();"
        f"return null;"
        f"}})()"
    )
    mcp.execute_js(submit_js, window_label=window_label)

    # Step 2: poll. Each poll returns `JSON.stringify(window[slot])` — "null"
    # while pending, a JSON object once the Promise settles.
    poll_js = (
        f"JSON.stringify(window[{json.dumps(slot)}])"
    )
    deadline = time.monotonic() + deadline_s
    settled: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        raw = mcp.execute_js(poll_js, window_label=window_label)
        if raw in ("null", "undefined", None, ""):
            time.sleep(poll_interval_s)
            continue
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            # Keep trying in case the bridge returned partial / coerced output
            # from a transient race; abort if we see structurally invalid data
            # repeatedly.
            raise IPCError(
                f"non-JSON poll response from {command!r}: {raw!r}"
            ) from e
        if parsed is None:
            time.sleep(poll_interval_s)
            continue
        settled = parsed
        break

    # Step 3: clear the slot so we don't leak state into subsequent calls.
    clear_js = f"delete window[{json.dumps(slot)}]; null"
    try:
        mcp.execute_js(clear_js, window_label=window_label)
    except Exception:  # noqa: BLE001
        pass  # best-effort cleanup; test should not fail on stale slot deletion

    if settled is None:
        raise IPCError(
            f"invoke {command!r} did not settle within {deadline_s}s"
        )
    if not isinstance(settled, dict):
        raise IPCError(
            f"unexpected slot shape from {command!r}: {settled!r}"
        )
    if settled.get("ok") is True:
        return settled.get("value")
    # err branch — either {ok: false, err: "..."} or a legacy {__tauri_error__:
    # "..."} (kept for back-compat with any test that still manually produces
    # that shape).
    if "err" in settled:
        raise IPCError(str(settled["err"]))
    if "__tauri_error__" in settled:
        raise IPCError(str(settled["__tauri_error__"]))
    raise IPCError(f"unknown slot shape from {command!r}: {settled!r}")
