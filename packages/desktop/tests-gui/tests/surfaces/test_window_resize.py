"""Responsive-layout tests for the main Tauri window.

These tests are currently **xfail(strict=True)** because the test harness
has no capability to resize the Tauri window:

  - ``gpd_tests/drivers/mcp.py`` (tauri-plugin-mcp client) exposes
    ``list_windows``, ``take_screenshot``, ``navigate_webview``, ``execute_js``
    and ``restart_app`` — none of which set window size or bounds.
  - ``gpd_tests/fixtures/tauri_commands.json`` (auto-generated catalog of
    ``#[tauri::command]`` functions registered by the debug binary) contains
    no ``set_size`` / ``resize`` / ``set_bounds`` entries — the product does
    not expose a resize command to the webview.
  - ``window.resizeTo(w, h)`` from JS is a no-op in Tauri WKWebView unless
    explicitly permitted by capability; it is not.
  - AppleScript ``set bounds`` against the ``System Events`` process is
    blocked by macOS accessibility unless GPD Dev is granted Screen
    Recording AND Accessibility permissions, neither of which the harness
    assumes.

When any one of the above lands (e.g. a new ``resize_window`` MCP command,
a ``set_window_size`` Tauri command, or an ``os_input.resize_window``
helper), drop the xfail marker and flesh out the assertions.
"""
from __future__ import annotations

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_home


_HARNESS_MISSING_REASON = (
    "Harness lacks window-resize capability: MCPClient has no resize method, "
    "tauri_commands.json exposes no set_size/resize/set_bounds command, and "
    "window.resizeTo is a no-op in Tauri WKWebView. Re-enable when a resize "
    "driver lands (new MCP command, Tauri command, or AX-based helper)."
)


def _try_resize_window(mcp, width: int, height: int) -> bool:
    """Best-effort resize attempt. Returns True if the resize appeared to take.

    Tries (in order):
      1. ``window.resizeTo(width, height)`` via execute_js — confirmed no-op
         in Tauri WKWebView, kept for forward-compat with future webview
         runtimes.
      2. A hypothetical ``set_window_size`` MCP command via
         ``mcp._call`` — today the server returns "unknown command" but this
         path unblocks the tests the day such a command is added.

    Returns False on any failure so the test can xfail cleanly.
    """
    probe = DOMProbe(mcp)
    # Attempt 1: window.resizeTo — documented no-op in Tauri, but harmless.
    try:
        before = probe.eval(
            '(() => JSON.stringify({w: window.innerWidth, h: window.innerHeight}))()'
        )
        probe.eval(f'(() => {{ window.resizeTo({width}, {height}); return "ok"; }})()')
        after = probe.eval(
            '(() => JSON.stringify({w: window.innerWidth, h: window.innerHeight}))()'
        )
        import json as _json
        b = _json.loads(before)
        a = _json.loads(after)
        # Only consider the resize successful if innerWidth actually shrank to
        # within a tolerance of the requested value (Tauri will not reflect
        # resizeTo, so this branch stays False until the webview supports it).
        if abs(a.get("w", 0) - width) < 32 and abs(a.get("h", 0) - height) < 32:
            if (a.get("w") != b.get("w")) or (a.get("h") != b.get("h")):
                return True
    except ProbeSkip:
        return False
    except Exception:
        pass

    # Attempt 2: speculative MCP command — will fail today, will succeed the
    # day tauri-plugin-mcp exposes a resize. Wrapped in broad except because
    # MCPError / MCPTimeout are both expected failure modes here.
    try:
        mcp._call("set_window_size", {"width": width, "height": height})
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 1. Sidebar auto-collapse at narrow width
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.xfail(strict=True, reason=_HARNESS_MISSING_REASON)
def test_sidebar_auto_collapses_below_narrow_width(mcp, os_input):
    """Resize the window below the sidebar breakpoint and assert the sidebar
    transitions to its collapsed/hidden state.

    Expected observable (when implemented):
      - ``[data-component="sidebar"][data-state="collapsed"]`` present, OR
      - ``getComputedStyle(sidebar).width`` shrinks to the collapsed-rail
        width (<= 64px), OR
      - the sidebar has ``aria-hidden="true"`` at narrow widths.

    Today: the resize call itself fails, so this test xfails at the resize
    step before reaching any assertion.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)

    resized = _try_resize_window(mcp, width=480, height=900)
    assert resized, "window resize to 480x900 did not take effect"

    probe = DOMProbe(mcp)
    try:
        collapsed = probe.eval_bool(
            '(() => {'
            '  const sb = document.querySelector("[data-component=\\"sidebar\\"]");'
            '  if (!sb) return false;'
            '  const state = sb.getAttribute("data-state") || "";'
            '  if (state === "collapsed" || state === "hidden") return true;'
            '  if (sb.getAttribute("aria-hidden") === "true") return true;'
            '  const cs = getComputedStyle(sb);'
            '  const w = parseFloat(cs.width || "0");'
            '  return isFinite(w) && w <= 64;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    assert collapsed, "sidebar did not collapse at 480px viewport width"


# ---------------------------------------------------------------------------
# 2. Prompt input wraps at narrow width
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.xfail(strict=True, reason=_HARNESS_MISSING_REASON)
def test_prompt_input_wraps_at_narrow_width(mcp, os_input):
    """Resize the window below the composer breakpoint and assert the
    prompt-input block switches to a stacked/wrapped layout.

    Expected observable (when implemented):
      - prompt-input's computed ``flex-direction`` becomes ``column``, OR
      - scrollHeight > clientHeight (content wraps to a second line), OR
      - a ``data-layout="stacked"`` attribute is applied to the composer.

    Today: the resize call itself fails, so this test xfails at the resize
    step before reaching any assertion.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)

    resized = _try_resize_window(mcp, width=420, height=900)
    assert resized, "window resize to 420x900 did not take effect"

    probe = DOMProbe(mcp)
    try:
        wrapped = probe.eval_bool(
            '(() => {'
            '  const composer = document.querySelector('
            '    "[data-component=\\"prompt-input\\"], [data-slot=\\"prompt-input\\"]"'
            '  );'
            '  if (!composer) return false;'
            '  if ((composer.getAttribute("data-layout") || "") === "stacked") return true;'
            '  const cs = getComputedStyle(composer);'
            '  if ((cs.flexDirection || "").toLowerCase() === "column") return true;'
            '  return composer.scrollHeight > composer.clientHeight + 1;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    assert wrapped, "prompt-input did not wrap/stack at 420px viewport width"
