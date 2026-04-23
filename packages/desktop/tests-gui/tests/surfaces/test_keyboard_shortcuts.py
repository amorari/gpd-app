"""Phase G5.x — surface tests for global keyboard shortcuts.

Covers shortcuts registered by ``packages/app/src/pages/layout.tsx`` via the
``useCommand`` context, session-scoped commands in
``packages/app/src/pages/session/use-session-commands.tsx``, and the native
menu in ``packages/desktop/src/menu.ts``:

  - ``mod+comma``    → settings.open         (opens DialogSettings)
  - ``mod+b``        → sidebar.toggle        (toggles store.sidebar.opened)
  - ``mod+shift+s``  → session.new           (use-session-commands.tsx:357
                                              + menu.ts:68 accelerator)
  - ``escape``       → closes the top dialog (Kobalte default)
  - ``mod+k``        → file.open             (use-session-commands.tsx:399;
                                              keybind "mod+k,mod+p" where the
                                              comma is an ALTERNATE binding,
                                              not a chord)

The ``drivers.os_input`` ``press_key`` helper does not support modifier keys —
it's a bare ``osascript ... key code`` shim (see ``os_input.py`` line 94).
The rest of the suite uses the modifier-capable AppleScript ``keystroke``
pattern directly (e.g. ``test_dialog_settings.py:56``). We mirror that here
so shortcuts travel through the same AppKit path users hit in practice.

Note: ``test_cmd_comma_opens_settings_dialog`` overlaps with
``tests/surfaces/test_dialog_settings.py::test_settings_opens_via_cmd_comma_and_closes_on_escape``.
The settings-file test prefers a DOM-click fallback; the test here exercises
the pure-keystroke path. We keep both as they cover different focus paths.
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


def _ensure_frontmost(ax) -> None:
    """Activate the GPD app so AppleScript keystrokes land on its window.

    Mirrors the ``ax.activate()`` pattern from
    ``tests/surfaces/test_dialog_settings.py:50``. Without this guard a
    keystroke can hit the Terminal / IDE that's driving pytest and the
    test fails for reasons unrelated to the keybind registration.
    """
    try:
        ax.activate()
    except Exception:  # noqa: BLE001 — ax driver may be unavailable
        pass
    time.sleep(0.15)


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


def _close_any_open_dialog(mcp, os_input, ax) -> None:
    """Precondition: command.tsx early-returns on mod+comma when a dialog
    is already stacked. Clear the modal stack before each test."""
    probe = DOMProbe(mcp)
    try:
        if _any_dialog_open(probe):
            _ensure_frontmost(ax)
            os_input.press_key("escape")
            time.sleep(0.2)
    except ProbeSkip:
        pass


# --- tests ---------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.steals_focus
def test_cmd_comma_opens_settings_dialog(mcp, ax, os_input):
    """Cmd+, invokes the ``settings.open`` command bound at layout.tsx:1129.

    Overlaps with ``test_dialog_settings.py::test_settings_opens_via_cmd_comma_and_closes_on_escape``,
    which prefers a DOM-click fallback. Here we exercise the pure-keystroke
    path so a keybind regression (vs. a click regression) surfaces
    independently.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    _close_any_open_dialog(mcp, os_input, ax)
    probe = DOMProbe(mcp)

    _ensure_frontmost(ax)
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
    _ensure_frontmost(ax)
    os_input.press_key("escape")
    time.sleep(0.2)


@pytest.mark.surfaces
@pytest.mark.steals_focus
def test_cmd_b_toggles_sidebar_visibility(mcp, ax, os_input):
    """Cmd+B invokes the ``sidebar.toggle`` command bound at layout.tsx:1089.

    The toggle flips ``store.sidebar.opened`` (see ``context/layout.tsx:764``);
    the sidebar panel mirrors that into ``aria-hidden`` on the div sibling of
    ``[data-component="sidebar-rail"]`` (``sidebar-shell.tsx:132``). We read
    that aria attribute to observe the state change without touching internals.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    _close_any_open_dialog(mcp, os_input, ax)
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

    _ensure_frontmost(ax)
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

    _ensure_frontmost(ax)
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
@pytest.mark.steals_focus
def test_cmd_n_opens_new_session_affordance(mcp, ax, os_input):
    """Cmd+N is NOT bound in GPD — the ``session.new`` command lives at
    ``mod+shift+s`` (``use-session-commands.tsx:357`` + ``menu.ts:68``
    ``Shift+Cmd+S`` accelerator). We exercise the real shortcut here so the
    coverage gap is closed: send Cmd+Shift+S and assert the URL route
    changes (NewSessionView has no dedicated ``data-component`` anchor, so
    the URL is the only reliable signal).
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    _close_any_open_dialog(mcp, os_input, ax)

    url_before = mcp.current_url()

    # session.new is bound to mod+shift+s, not mod+n. Native menu accelerator
    # in menu.ts:68 is "Shift+Cmd+S"; the same id is registered via
    # useCommand in use-session-commands.tsx:357. Either handler taking the
    # navigate() branch flips the URL to ``/<dir>/session``, which is our
    # observable.
    _ensure_frontmost(ax)
    _keystroke("s", modifiers=["command", "shift"])

    deadline = time.monotonic() + 3.0
    route_changed = False
    url_now = url_before
    while time.monotonic() < deadline:
        url_now = mcp.current_url()
        if url_now != url_before:
            route_changed = True
            break
        time.sleep(0.1)

    assert route_changed, (
        "Cmd+Shift+S did not change the URL within 3s "
        f"(url_before={url_before!r}, url_now={url_now!r})"
    )


@pytest.mark.surfaces
@pytest.mark.steals_focus
def test_esc_closes_top_dialog(mcp, ax, os_input):
    """Escape closes the top Kobalte dialog (same path used for any modal).

    Open settings via Cmd+, then send Escape and assert the ``.settings-dialog``
    anchor disappears.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    _close_any_open_dialog(mcp, os_input, ax)
    probe = DOMProbe(mcp)

    _ensure_frontmost(ax)
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

    _ensure_frontmost(ax)
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


@pytest.mark.surfaces
@pytest.mark.steals_focus
def test_cmd_k_opens_file_picker(mcp, ax, http, os_input, git_project_dir):
    """Cmd+K invokes the ``file.open`` command (``use-session-commands.tsx:399``).

    The keybind string ``mod+k,mod+p`` registers TWO alternate bindings —
    the comma is NOT a chord separator, it's the useCommand map's way of
    listing alternates. Pressing Cmd+K calls ``openFile()`` in
    use-session-commands.tsx:215, which dynamically imports
    ``DialogSelectFile`` and shows it via the dialog stack. We assert that
    a new dialog (``[data-component="dialog"]``) appears within 3s.
    """
    ses = http.create_session(directory=str(git_project_dir))
    sid = ses["id"]
    dir_token = encode_dir_token(str(git_project_dir))
    Navigator(mcp).go(
        route_session_in_project(dir_token, sid), timeout_s=8.0
    )
    _close_any_open_dialog(mcp, os_input, ax)

    probe = DOMProbe(mcp)
    # Wait for prompt-input to mount — it's a proxy for "session view ready".
    # If the session view hasn't mounted, the file.open command isn't even
    # registered yet (it's scoped to useSessionCommands).
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

    # Snapshot any pre-existing dialog so we can distinguish "Cmd+K opened a
    # dialog" from "a dialog was already there" (defensive — _close_any_open_dialog
    # above should have cleared it, but the guard is cheap).
    try:
        dialog_before = probe.eval_bool(
            '(() => !!document.querySelector('
            '"[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
            '))()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if dialog_before:
        pytest.skip("pre-existing dialog couldn't be cleared; can't attribute Cmd+K effect")

    _ensure_frontmost(ax)
    _keystroke("k", modifiers=["command"])

    deadline = time.monotonic() + 3.0
    opened = False
    while time.monotonic() < deadline:
        try:
            opened = probe.eval_bool(
                '(() => !!document.querySelector('
                '"[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                '))()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if opened:
            break
        time.sleep(0.1)

    assert opened, "Cmd+K did not open the file picker / command palette dialog within 3s"

    # Cleanup — don't leak the dialog into the next test.
    _ensure_frontmost(ax)
    os_input.press_key("escape")
    time.sleep(0.2)
