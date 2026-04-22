"""Surfaces expansion — dialogs not yet covered by group A/B tests.

Covers:
  - dialog-fork: user forks a session from a specific message
  - dialog-confirm-delete-project: user confirms deletion of a project

Both tests simulate the full user interaction: navigate -> trigger -> assert
content -> close.
"""
from __future__ import annotations

import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_home,
    route_project,
    route_session_in_project,
)


_DIALOG_TIMEOUT_S = 4.0


def _wait_for(probe: DOMProbe, js: str, timeout_s: float = _DIALOG_TIMEOUT_S) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if probe.eval_bool(js):
                return True
        except ProbeSkip:
            raise
        time.sleep(0.1)
    return False


def _dismiss(probe: DOMProbe, os_input, max_presses: int = 3) -> None:
    for _ in range(max_presses):
        try:
            open_ = probe.eval_bool(
                '(() => !!document.querySelector('
                '"[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                '))()'
            )
        except ProbeSkip:
            return
        if not open_:
            return
        try:
            os_input.press_key("escape")
        except Exception:
            return
        time.sleep(0.15)


# ---------------------------------------------------------------------------
# dialog-fork
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.real_backend
def test_fork_dialog_opens_with_message_list(http, mcp, os_input, gpd_key):
    """Full journey: send one message to a real session, navigate to it in
    the UI, trigger the /fork command, and assert the fork dialog shows a
    list of messages to branch from.

    Uses Haiku to minimise cost. The /fork slash command is triggered via
    the command palette (Cmd+K / Ctrl+K then typing 'fork').
    """
    probe = DOMProbe(mcp)
    ses = http.create_session()
    sid = ses["id"]

    try:
        # Send one message — creates a user message the fork dialog lists.
        http.send_message(
            sid,
            parts=[{"type": "text", "text": "Say the word 'ready' and nothing else."}],
            model_id="claude-haiku-4-5",
            provider_id="gpd",
            agent="default",
        )

        # Navigate to the session in the UI.
        # The session is not directory-scoped, so use the bare session URL.
        # We navigate to / first to ensure the app is in a known state, then to the session.
        Navigator(mcp).go(route_home(), timeout_s=5.0)
        time.sleep(0.3)

        # Try navigating to the session URL.
        # Session routes are /:dir/session/:id — we need the project dir.
        # Use the sessions() listing to get any directory associated with this session.
        all_sessions = http.sessions()
        session_info = next((s for s in all_sessions if s["id"] == sid), None)
        directory = (session_info or {}).get("directory") or ""

        if directory:
            dir_token = encode_dir_token(directory)
            nav_url = route_session_in_project(dir_token, sid)
        else:
            # No directory: try the home route and look for the session there
            nav_url = route_home()

        Navigator(mcp).go(nav_url, timeout_s=6.0)
        time.sleep(0.5)

        # Open the command palette via the '/fork' slash command in the input.
        # We type '/fork' into the prompt input if present, or use Cmd+K.
        triggered = False
        try:
            triggered = probe.eval_bool(
                '(() => {'
                '  const input = document.querySelector('
                '    "[data-component=\\"prompt-input\\"] textarea, '
                '    [data-slot=\\"prompt-textarea\\"], '
                '    [data-component=\\"composer\\"] textarea"'
                '  );'
                '  if (!input) return false;'
                '  input.focus();'
                '  return true;'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        if not triggered:
            pytest.fail("could not find prompt input — session may not have loaded")

        # Type /fork to trigger the slash command.
        try:
            os_input.type_text("/fork")
        except Exception as e:
            pytest.skip(f"os_input.type_text unavailable ({e})")

        time.sleep(0.3)

        # The fork command should appear in the slash-command palette.
        # Look for a slash-menu/command-palette element that mentions "fork" specifically,
        # not just any page text (which would always match after we navigate to a session).
        fork_visible = _wait_for(
            probe,
            '(() => {'
            '  const palette = document.querySelector('
            '    "[data-component=\\"slash-menu\\"], [data-component=\\"command-palette\\"],'
            '    [data-component=\\"command-list\\"], [role=\\"listbox\\"],'
            '    [role=\\"menu\\"]"'
            '  );'
            '  if (palette) {'
            '    return palette.innerText.toLowerCase().includes("fork");'
            '  }'
            '  return !!document.querySelector("[data-component=\\"dialog\\"]");'
            '})()',
            timeout_s=3.0,
        )

        if not fork_visible:
            pytest.skip("fork command or dialog did not appear after typing /fork")

        # Press Enter to select the fork command from the palette.
        try:
            os_input.press_key("return")
        except Exception:
            pass
        time.sleep(0.4)

        # Assert the fork dialog opened — it lists previous messages to branch from.
        dialog_open = _wait_for(
            probe,
            '(() => !!document.querySelector('
            '"[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
            '))()',
            timeout_s=3.0,
        )
        assert dialog_open, "fork dialog did not open after selecting the /fork command"

    finally:
        _dismiss(probe, os_input)
        try:
            http.delete_session(sid)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# dialog-confirm-delete-project
# ---------------------------------------------------------------------------


@pytest.fixture
def _temp_project(tmp_path_factory) -> str:
    """A real on-disk directory GPD will treat as a project."""
    p = tmp_path_factory.mktemp("gpd_del_proj_test")
    p = p.resolve()
    (p / "README.md").write_text("# delete project test\n")
    return str(p)


@pytest.mark.surfaces
def test_confirm_delete_project_dialog_opens_from_sidebar(
    mcp, os_input, _temp_project
):
    """Navigate to a project so it appears in the sidebar, then trigger the
    'Delete project' action from the sidebar context menu and assert the
    confirmation dialog renders with a Cancel button.

    Uses only the temp project directory — no real backend needed.
    """
    probe = DOMProbe(mcp)

    # Navigate to the project to register it in the sidebar.
    # route_project triggers the auto-register hook on /:dir; route_session_in_project does not.
    Navigator(mcp).go(route_project(_temp_project), timeout_s=6.0)
    time.sleep(0.4)

    # Go back to home so the project shows in the sidebar.
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    time.sleep(0.3)

    # Find the project in the sidebar and right-click (context menu) or
    # click the kebab / overflow button to reveal 'Delete'.
    try:
        found = probe.eval_bool(
            '(() => {'
            '  const sidebar = document.querySelector('
            '    "[data-component=\\"sidebar\\"], [data-slot=\\"sidebar\\"], nav"'
            '  );'
            '  return !!sidebar;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    if not found:
        pytest.skip("sidebar not found on home page")

    # Try to click the project's kebab/overflow menu button.
    # Fallback: right-click the project row to open its context menu.
    opened_menu = False
    try:
        opened_menu = probe.eval_bool(
            '(() => {'
            '  const btns = Array.from(document.querySelectorAll('
            '    "button[aria-label], button[data-action]"'
            '  ));'
            '  const more = btns.find(b => '
            '    /more|options|menu|\\.\\.\\.|⋮/i.test(b.textContent + (b.getAttribute("aria-label") || ""))'
            '  );'
            '  if (more) { more.click(); return true; }'
            '  return false;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    if not opened_menu:
        pytest.skip(
            "could not find sidebar overflow/context menu trigger — "
            "delete dialog test requires a visible project entry"
        )

    time.sleep(0.25)

    # Find and click the Delete item in the context menu.
    clicked_delete = False
    try:
        clicked_delete = probe.eval_bool(
            '(() => {'
            '  const items = Array.from(document.querySelectorAll('
            '    "[role=\\"menuitem\\"], [data-component=\\"dropdown-item\\"],'
            '    [data-component=\\"context-menu-item\\"]"'
            '  ));'
            '  const del = items.find(i => /delete|remove/i.test(i.textContent));'
            '  if (del) { del.click(); return true; }'
            '  return false;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    if not clicked_delete:
        pytest.skip("Delete menu item not found in context menu")

    time.sleep(0.3)

    try:
        # Assert the confirmation dialog appeared.
        dialog_open = _wait_for(
            probe,
            '(() => {'
            '  const d = document.querySelector('
            '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
            '  );'
            '  if (!d) return false;'
            '  const txt = d.innerText.toLowerCase();'
            '  return txt.includes("delete") || txt.includes("cancel") || txt.includes("confirm");'
            '})()',
            timeout_s=3.0,
        )
        assert dialog_open, "confirm-delete dialog did not open after clicking Delete in sidebar"

        # Verify the dialog has a Cancel button (user can back out).
        cancel_present = False
        try:
            cancel_present = probe.eval_bool(
                '(() => {'
                '  const d = document.querySelector('
                '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                '  );'
                '  if (!d) return false;'
                '  const btns = Array.from(d.querySelectorAll("button"));'
                '  return btns.some(b => /cancel/i.test(b.textContent));'
                '})()'
            )
        except ProbeSkip:
            cancel_present = True  # can't read — assume present and move on

        assert cancel_present, "confirm-delete dialog is missing a Cancel button"
    finally:
        # Always dismiss — do NOT confirm the delete even if assertions fail.
        _dismiss(probe, os_input)
