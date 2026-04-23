"""Phase G5.x — surface tests for global keyboard shortcuts.

Covers shortcuts registered by ``packages/app/src/pages/layout.tsx`` via the
``useCommand`` context and the native menu in ``packages/desktop/src/menu.ts``:

  - ``mod+comma``    → settings.open         (opens DialogSettings)
  - ``mod+b``        → sidebar.toggle        (toggles store.sidebar.opened)
  - ``mod+shift+s``  → session.new           (native menu + command)
  - ``escape``       → closes the top dialog (Kobalte default)
  - ``mod+k``        → NOT BOUND in GPD      (xfail(strict=True))

The ``drivers.os_input`` ``press_key`` helper does not support modifier keys —
it's a bare ``osascript ... key code`` shim (see ``os_input.py`` line 94).
The rest of the suite uses the modifier-capable AppleScript ``keystroke``
pattern directly (e.g. ``test_dialog_settings.py:56``). We mirror that here
so shortcuts travel through the same AppKit path users hit in practice.
"""
from __future__ import annotations

import subprocess
import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_home,
    route_session_in_project,
)


# --- local helpers -------------------------------------------------------


def _keystroke(char: str, *, modifiers: list[str]) -> None:
    """Send ``char`` as an AppleScript keystroke with the given modifiers.

    ``modifiers`` is a list of names: "command", "shift", "option",
    "control". Escapes the quote so characters like ``"`` wouldn't break
    the AppleScript (overkill for our use — only single ASCII chars go
    through — but cheap).
    """
    escaped = char.replace("\\", "\\\\").replace('"', '\\"')
    using = ", ".join(f"{m} down" for m in modifiers)
    script = (
        f'tell application "System Events" to keystroke "{escaped}" using {{{using}}}'
    )
    subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        check=True,
        timeout=5.0,
    )


def _keycode(code: int, *, modifiers: list[str] | None = None) -> None:
    """Send a macOS key code. Used for non-character keys (arrows/fn) if needed."""
    if modifiers:
        using = ", ".join(f"{m} down" for m in modifiers)
        script = f'tell application "System Events" to key code {code} using {{{using}}}'
    else:
        script = f'tell application "System Events" to key code {code}'
    subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        check=True,
        timeout=5.0,
    )


def _settings_dialog_open(probe: DOMProbe) -> bool:
    """Return True iff the settings dialog (``.settings-dialog``) is mounted."""
    return probe.eval_bool(
        '(() => !!document.querySelector('
        '"[data-component=\\"dialog\\"] .settings-dialog, '
        '.settings-dialog"'
        '))()'
    )


def _any_dialog_open(probe: DOMProbe) -> bool:
    return probe.eval_bool(
        '(() => !!document.querySelector('
        '"[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
        '))()'
    )


def _close_any_open_dialog(mcp, os_input) -> None:
    """Precondition: command.tsx early-returns on mod+comma when a dialog
    is already stacked. Clear the modal stack before each test."""
    probe = DOMProbe(mcp)
    try:
        if _any_dialog_open(probe):
            os_input.press_key("escape")
            time.sleep(0.2)
    except ProbeSkip:
        pass


# --- tests ---------------------------------------------------------------


@pytest.mark.surfaces
def test_cmd_comma_opens_settings_dialog(mcp, os_input):
    """Cmd+, invokes the ``settings.open`` command bound at layout.tsx:1132."""
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    _close_any_open_dialog(mcp, os_input)
    probe = DOMProbe(mcp)

    _keystroke(",", modifiers=["command"])

    deadline = time.monotonic() + 3.0
    opened = False
    while time.monotonic() < deadline:
        try:
            opened = _settings_dialog_open(probe)
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if opened:
            break
        time.sleep(0.1)

    assert opened, "settings dialog did not appear within 3s of Cmd+,"

    # Cleanup — don't leak an open dialog into the next test.
    os_input.press_key("escape")
    time.sleep(0.2)


@pytest.mark.surfaces
def test_cmd_b_toggles_sidebar_visibility(mcp, os_input):
    """Cmd+B invokes the ``sidebar.toggle`` command bound at layout.tsx:1092.

    The toggle flips ``store.sidebar.opened`` (see ``context/layout.tsx:764``);
    the sidebar panel mirrors that into ``aria-hidden`` on the div sibling of
    ``[data-component="sidebar-rail"]`` (``sidebar-shell.tsx:132``). We read
    that aria attribute to observe the state change without touching internals.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    _close_any_open_dialog(mcp, os_input)
    probe = DOMProbe(mcp)

    read_expanded = (
        '(() => {'
        '  const rail = document.querySelector("[data-component=\\"sidebar-rail\\"]");'
        '  if (!rail) return null;'
        '  const panel = rail.nextElementSibling;'
        '  if (!panel) return null;'
        '  return panel.getAttribute("aria-hidden") === "true" ? "0" : "1";'
        '})()'
    )
    try:
        before = probe.eval(read_expanded)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if before in (None, "null", "", "undefined"):
        pytest.skip("sidebar-rail not found on home surface; nothing to toggle")

    _keystroke("b", modifiers=["command"])

    deadline = time.monotonic() + 3.0
    after = before
    while time.monotonic() < deadline:
        after = probe.eval(read_expanded)
        if after != before:
            break
        time.sleep(0.1)
    assert after != before, (
        f"Cmd+B did not toggle sidebar visibility (before={before!r}, after={after!r})"
    )

    _keystroke("b", modifiers=["command"])
    deadline = time.monotonic() + 3.0
    reverted = after
    while time.monotonic() < deadline:
        reverted = probe.eval(read_expanded)
        if reverted == before:
            break
        time.sleep(0.1)
    assert reverted == before, (
        f"second Cmd+B did not revert sidebar (before={before!r}, reverted={reverted!r})"
    )


@pytest.mark.surfaces
def test_cmd_n_opens_new_session_affordance(mcp, os_input):
    """Cmd+N is NOT bound in GPD — the ``session.new`` command lives at
    ``mod+shift+s`` (layout.tsx:1260 + menu.ts:68). We still exercise the
    primary new-session shortcut so the coverage gap is closed: send
    Cmd+Shift+S and assert either a new route (``/session/<id>``) or a
    new-session affordance (dialog or new-view card) becomes visible.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    _close_any_open_dialog(mcp, os_input)
    probe = DOMProbe(mcp)

    url_before = mcp.current_url()

    # session.new is bound to mod+shift+s, not mod+n. Native menu accelerator
    # in menu.ts:68 uses "Shift+Cmd+S". Test that shortcut; xfail if neither
    # the URL nor the DOM shows a new-session affordance.
    _keystroke("s", modifiers=["command", "shift"])

    deadline = time.monotonic() + 3.0
    affordance = False
    while time.monotonic() < deadline:
        try:
            url_now = mcp.current_url()
            route_changed = url_now != url_before
            new_view = probe.eval_bool(
                '(() => !!document.querySelector('
                '"[data-component=\\"session-new-view\\"], '
                '[data-component=\\"dialog\\"] [data-new-session]"'
                '))()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if route_changed or new_view:
            affordance = True
            break
        time.sleep(0.1)

    assert affordance, (
        "Cmd+Shift+S did not yield a new-session affordance within 3s "
        f"(url_before={url_before!r}, url_now={mcp.current_url()!r})"
    )


@pytest.mark.surfaces
def test_esc_closes_top_dialog(mcp, os_input):
    """Escape closes the top Kobalte dialog (same path used for any modal).

    Open settings via Cmd+, then send Escape and assert the ``.settings-dialog``
    anchor disappears.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    _close_any_open_dialog(mcp, os_input)
    probe = DOMProbe(mcp)

    _keystroke(",", modifiers=["command"])
    deadline = time.monotonic() + 3.0
    opened = False
    while time.monotonic() < deadline:
        try:
            opened = _settings_dialog_open(probe)
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if opened:
            break
        time.sleep(0.1)
    if not opened:
        pytest.skip("settings dialog never opened — cannot test Escape close")

    os_input.press_key("escape")

    deadline = time.monotonic() + 3.0
    still_open = True
    while time.monotonic() < deadline:
        try:
            still_open = _settings_dialog_open(probe)
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if not still_open:
            break
        time.sleep(0.1)
    assert not still_open, "settings dialog did not close on Escape"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Cmd+K is not registered in the GPD command palette. The useCommand "
        "keybind map in packages/app/src/pages/layout.tsx has no entry for "
        "'mod+k' that focuses the prompt input. If this fails (i.e. starts "
        "passing), a binding was added — remove the xfail."
    ),
)
@pytest.mark.surfaces
def test_cmd_k_focuses_prompt_input_when_in_session(mcp, http, os_input, git_project_dir):
    """Cmd+K should focus the ``[data-component="prompt-input"]`` editor.

    Not currently bound in GPD — asserted as ``xfail(strict=True)``. When the
    binding lands this test will start passing and fail loudly (XPASS) so
    the xfail is a tripwire, not dead code.
    """
    ses = http.create_session(directory=str(git_project_dir))
    sid = ses["id"]
    dir_token = encode_dir_token(str(git_project_dir))
    Navigator(mcp).go(
        route_session_in_project(dir_token, sid), timeout_s=8.0
    )
    _close_any_open_dialog(mcp, os_input)

    probe = DOMProbe(mcp)
    # Wait for prompt-input to mount before the keystroke — otherwise a slow
    # mount would look like a binding failure.
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            present = probe.eval_bool(
                '!!document.querySelector("[data-component=\\"prompt-input\\"]")'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if present:
            break
        time.sleep(0.1)
    else:
        pytest.skip("prompt-input never mounted in session view")

    # Defensively blur whatever is focused so the assertion below actually
    # reflects Cmd+K's effect, not residual focus from the nav sequence.
    try:
        probe.eval(
            '(() => { const a = document.activeElement;'
            ' if (a && a.blur) a.blur(); document.body.focus?.(); })()'
        )
    except ProbeSkip:
        pass

    _keystroke("k", modifiers=["command"])

    deadline = time.monotonic() + 3.0
    focused = False
    while time.monotonic() < deadline:
        try:
            focused = probe.eval_bool(
                '(() => {'
                '  const pi = document.querySelector("[data-component=\\"prompt-input\\"]");'
                '  if (!pi) return false;'
                '  const a = document.activeElement;'
                '  return a === pi || pi.contains(a);'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if focused:
            break
        time.sleep(0.1)

    assert focused, "Cmd+K did not focus prompt-input"
