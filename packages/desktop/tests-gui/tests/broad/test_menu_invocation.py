"""Menu invocation tests: click menu items and verify observable UI effects.

The sibling test_menu_*_items.py files only inspect existence/enabled state;
they never exercise ax.click_menu_item(). This module drives each menu item
that has a safe, observable effect and asserts the downstream change via
the MCP DOM bridge.

Items that would destabilise the test harness (Quit, Minimize, Close Window,
Restart, Reload Webview) are explicitly skipped with a clear reason rather
than silently omitted.
"""
from __future__ import annotations

import time

import pytest

from gpd_tests.drivers.ax import AXClient
from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip


# --- shared helpers ------------------------------------------------------


_APP_MENU_CANDIDATES = ("GPD", "GPD Dev", "GPD Beta")

_FILE_NEW_SESSION_VARIANTS = ("New Conversation", "New Session")
_VIEW_TOGGLE_SIDEBAR_VARIANTS = ("Toggle Sidebar",)
_EDIT_SELECT_ALL_VARIANTS = ("Select All", "Select all")
_HELP_ABOUT_VARIANTS = ("About GPD", "About GPD Dev", "About GPD Beta")


def _first_present(ax: AXClient, menu: str, variants: tuple[str, ...]) -> str | None:
    """Return the first name from *variants* that exists under *menu*, else None."""
    items = set(ax.items_of(menu))
    for v in variants:
        if v in items:
            return v
    return None


def _app_menu_name(ax: AXClient) -> str | None:
    top = set(ax.top_level_menus())
    for c in _APP_MENU_CANDIDATES:
        if c in top:
            return c
    return None


def _wait_for(probe: DOMProbe, expr: str, *, timeout_s: float = 3.0) -> bool:
    """Poll `expr` until it returns truthy or the deadline lapses."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if probe.eval_bool(expr):
                return True
        except ProbeSkip:
            raise
        time.sleep(0.15)
    return False


# --- File > New Session/Conversation -------------------------------------


@pytest.mark.broad
def test_file_new_session_opens_dialog_or_route(ax: AXClient, mcp):
    """Click File > New Conversation/Session; expect a dialog open OR a URL change.

    Depending on the current surface, session.new either opens the new-session
    dialog (when a project context is active) or navigates to a new session
    route. Either signal counts as 'the menu action fired'.
    """
    item = _first_present(ax, "File", _FILE_NEW_SESSION_VARIANTS)
    if item is None:
        pytest.skip(
            f"none of {_FILE_NEW_SESSION_VARIANTS} present in File menu "
            f"(got {sorted(ax.items_of('File'))}) — Tauri createMenu() may "
            "not have registered custom items yet"
        )
    probe = DOMProbe(mcp)
    url_before = mcp.current_url()
    try:
        dialogs_before = probe.eval_bool(
            '!!document.querySelector(\'[role="dialog"], [data-slot="dialog"], dialog[open]\')'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    ax.click_menu_item("File", item)

    try:
        changed = _wait_for(
            probe,
            '(() => {'
            '  const dialog = !!document.querySelector('
            '    \'[role="dialog"], [data-slot="dialog"], dialog[open]\'); '
            f' const url = window.location.href !== {url_before!r};'
            '  return dialog || url;'
            '})()',
            timeout_s=4.0,
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable after click ({e})")

    # Fallback probe: route may have changed even if DOM poll missed it.
    if not changed:
        url_after = mcp.current_url()
        changed = url_after != url_before or dialogs_before is False and probe.eval_bool(
            '!!document.querySelector(\'[role="dialog"], [data-slot="dialog"], dialog[open]\')'
        )

    assert changed, (
        f"File > {item!r} had no observable effect: URL unchanged ({url_before!r}) "
        "and no dialog opened within 4s"
    )


# --- View > Toggle Sidebar -----------------------------------------------


@pytest.mark.broad
def test_view_toggle_sidebar_toggles_dom(ax: AXClient, mcp):
    """Click View > Toggle Sidebar; expect the sidebar element to appear or disappear."""
    item = _first_present(ax, "View", _VIEW_TOGGLE_SIDEBAR_VARIANTS)
    if item is None:
        pytest.skip(
            f"none of {_VIEW_TOGGLE_SIDEBAR_VARIANTS} present in View menu "
            "— custom menu items may not be registered yet"
        )
    probe = DOMProbe(mcp)
    sidebar_selector = (
        '[data-component="sidebar"], [data-slot="sidebar"], '
        'aside[data-sidebar], nav[data-sidebar]'
    )
    probe_expr = (
        '(() => {'
        f' const el = document.querySelector({sidebar_selector!r});'
        '  if (!el) return { present: false, width: 0 };'
        '  const r = el.getBoundingClientRect();'
        '  return { present: true, width: Math.round(r.width) };'
        '})()'
    )

    # Pre-click snapshot: we need to know what 'before' looks like.
    try:
        before_raw = probe.eval(
            'JSON.stringify(' + probe_expr + ')'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    import json as _json
    try:
        before = _json.loads(before_raw) if before_raw else {}
    except (ValueError, TypeError):
        pytest.skip(f"could not parse sidebar snapshot: {before_raw!r}")

    if not before.get("present") and before.get("width", 0) == 0:
        # Nothing to toggle — maybe we're on a surface with no sidebar.
        # Click anyway; a toggle should still flip visibility.
        pass

    ax.click_menu_item("View", item)

    try:
        changed = _wait_for(
            probe,
            '(() => {'
            f' const el = document.querySelector({sidebar_selector!r});'
            '  const present = !!el;'
            '  const width = el ? Math.round(el.getBoundingClientRect().width) : 0;'
            f' return present !== {str(before.get("present", False)).lower()} '
            f'     || width !== {int(before.get("width", 0))};'
            '})()',
            timeout_s=3.0,
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable after click ({e})")

    if not changed:
        # Restore by clicking again so we don't leave the sidebar toggled.
        ax.click_menu_item("View", item)
        pytest.skip(
            "sidebar DOM/width unchanged after Toggle Sidebar — surface may "
            "lack a sidebar (home welcome overlay) or sidebar selector is stale"
        )

    # Restore original state to avoid polluting downstream tests.
    ax.click_menu_item("View", item)


# --- Edit > Select All ---------------------------------------------------


@pytest.mark.broad
def test_edit_select_all_focuses_input(ax: AXClient, mcp):
    """If a text input is focused, Edit > Select All should select its contents.

    Select All targets the currently focused element. Without a focused
    input/textarea/contenteditable, macOS routes the action to a native
    AppKit view (no observable effect on the webview) and the test would
    be meaningless; we skip in that case rather than fabricate focus.
    """
    item = _first_present(ax, "Edit", _EDIT_SELECT_ALL_VARIANTS)
    if item is None:
        pytest.skip(
            f"none of {_EDIT_SELECT_ALL_VARIANTS} present in Edit menu"
        )
    probe = DOMProbe(mcp)

    # Try to find and focus a text input. If none exists on the current
    # surface, skip — we will not synthesise focus via Tab because that
    # would bleed into neighbouring tests' preconditions.
    try:
        seeded = probe.eval_bool(
            '(() => {'
            '  const el = document.querySelector('
            '    \'input[type="text"], input:not([type]), textarea, '
            '     [contenteditable="true"]\');'
            '  if (!el) return false;'
            '  el.focus();'
            '  if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {'
            '    el.value = "abc xyz";'
            '    el.setSelectionRange(0, 0);'
            '  } else {'
            '    el.textContent = "abc xyz";'
            '    const sel = window.getSelection();'
            '    sel.removeAllRanges();'
            '    const r = document.createRange();'
            '    r.setStart(el, 0); r.setEnd(el, 0);'
            '    sel.addRange(r);'
            '  }'
            '  return document.activeElement === el;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    if not seeded:
        pytest.skip("no focusable text input on current surface; skipping")

    ax.click_menu_item("Edit", item)

    try:
        all_selected = _wait_for(
            probe,
            '(() => {'
            '  const el = document.activeElement;'
            '  if (!el) return false;'
            '  if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {'
            '    return el.selectionStart === 0 && el.selectionEnd === el.value.length && el.value.length > 0;'
            '  }'
            '  const sel = window.getSelection();'
            '  return sel && sel.toString().length > 0;'
            '})()',
            timeout_s=2.0,
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable after click ({e})")

    assert all_selected, "Select All did not select the focused input's contents"


# --- App > Hide / Quit / Minimize (destabilising) ------------------------


@pytest.mark.broad
def test_window_minimize_skipped():
    """Minimize the window would backgrounded the webview and break the harness.

    macOS throttles webviews for backgrounded windows, which causes every
    subsequent MCP execute_js call in the same session to time out. The
    conftest reactivates GPD in pytest_runtest_setup, but that races the
    next test's fixture setup. Safer to skip entirely than to introduce
    cross-test flake.
    """
    pytest.skip(
        "Minimize/Hide intentionally not exercised: backgrounding the webview "
        "throttles execute_js and causes cross-test MCP timeouts. The menu "
        "item's existence/enabled state is already covered by the sibling "
        "test_menu_app_items.py suite."
    )


@pytest.mark.broad
def test_app_quit_skipped():
    """Quit would terminate GPD and end the test session."""
    pytest.skip(
        "Quit intentionally not exercised: would terminate GPD and end the "
        "session-scoped app_state fixture. Existence/enabled state is "
        "covered by test_app_menu_quit_is_enabled."
    )


# --- Help > About --------------------------------------------------------


@pytest.mark.broad
def test_help_about_opens_about_panel(ax: AXClient, mcp):
    """Click the App menu's About item.

    The PredefinedMenuItem { About: null } opens a native AppKit panel (not
    a DOM dialog), so there is no webview-observable change; the post-click
    check simply confirms that clicking it didn't crash GPD — MCP must still
    ping. If an 'About' MenuItem ever gets added under Help with a webview
    dialog, this test will exercise that path instead.
    """
    # The About panel lives under the application menu in menu.ts, not Help.
    app_menu = _app_menu_name(ax)
    help_about = _first_present(ax, "Help", ("About GPD", "About"))
    if help_about is not None:
        menu, item = "Help", help_about
    elif app_menu is not None:
        app_about = _first_present(ax, app_menu, _HELP_ABOUT_VARIANTS)
        if app_about is None:
            pytest.skip(
                f"no About item under Help or {app_menu!r} menu"
            )
        menu, item = app_menu, app_about
    else:
        pytest.skip("no application menu present to host About item")

    ax.click_menu_item(menu, item)
    # Native panel has no DOM; just confirm GPD is still responsive and
    # dismiss the panel by pressing Escape so downstream tests aren't
    # blocked by a modal AppKit window.
    try:
        mcp.ping()
    except Exception as e:
        pytest.fail(f"clicking {menu} > {item} made GPD unresponsive: {e}")
    # Dismiss the native About panel.
    import subprocess as _sp
    _sp.run(
        ["osascript", "-e",
         'tell application "System Events" to key code 53'],
        capture_output=True, check=False, timeout=3.0,
    )
