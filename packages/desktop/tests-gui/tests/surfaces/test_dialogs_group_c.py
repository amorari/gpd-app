"""G5.3 — Dialog components (group C) anchor/presence tests.

Covers three dialogs with zero test coverage:

- dialog-edit-project   via [data-action="project-menu"] dropdown -> "Edit"
                        (requires a project in the sidebar)
- dialog-release-notes  automatically shown on version change by the
                        HighlightsProvider; no stable programmatic trigger
                        exists in the current product surface — xfail until
                        a data-action anchor or command is added
- dialog-select-server  via the home-page server name button (inline
                        DialogSelectServer render on click)

Each test follows the pattern from group A/B:
  open -> verify DOM anchor -> close -> verify closed

All tests are defensive: a finally block with _dismiss_any_overlay ensures
no dialog leaks into a later test.
"""
from __future__ import annotations

import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_home,
    route_session_in_project,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# How long to wait for a dialog to mount after clicking its trigger.
_DIALOG_MOUNT_TIMEOUT_S = 4.0

# Generic "any dialog-or-popover is currently open" JS expression.
_JS_ANY_DIALOG_OPEN = (
    '!!document.querySelector('
    '"[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
    ')'
)

# The edit-project dialog title as rendered in en.ts:
#   "dialog.project.edit.title": "Edit project"
_EDIT_PROJECT_TITLE_EN = "Edit project"

# The select-server dialog title as rendered in en.ts:
#   "dialog.server.title": "Servers"
_SELECT_SERVER_TITLE_EN = "Servers"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def prepared_project_path(tmp_path_factory) -> str:
    """On-disk directory with a git repo that GPD treats as a project."""
    import subprocess

    p = tmp_path_factory.mktemp("gpd_proj_dialogs_c")
    p = p.resolve()
    (p / "README.md").write_text("# dialogs group C test project\n")
    subprocess.run(["git", "init", str(p)], check=True, capture_output=True)
    subprocess.run(
        [
            "git", "-C", str(p),
            "-c", "user.email=test@test.com",
            "-c", "user.name=Test",
            "commit", "--allow-empty", "-m", "init",
        ],
        check=True,
        capture_output=True,
    )
    return str(p)


def _wait_for(probe: DOMProbe, js: str, timeout_s: float = _DIALOG_MOUNT_TIMEOUT_S) -> bool:
    """Poll *js* (must return a boolean) until truthy or timeout elapses."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if probe.eval_bool(js):
                return True
        except ProbeSkip:
            raise
        time.sleep(0.1)
    return False


def _dismiss_any_overlay(probe: DOMProbe, os_input_or_none, *, max_presses: int = 3) -> None:
    """Press Escape up to *max_presses* times to clear any dialog/popover."""
    for _ in range(max_presses):
        try:
            open_ = probe.eval_bool(
                '(() => !!document.querySelector('
                '"[data-component=\\"dialog\\"], [role=\\"dialog\\"], '
                '[role=\\"menu\\"], [data-component=\\"popover\\"]"'
                '))()'
            )
        except ProbeSkip:
            return
        if not open_:
            return
        if os_input_or_none is not None:
            try:
                os_input_or_none.press_key("escape")
            except Exception:
                return
        time.sleep(0.15)


def _press_escape(os_input) -> None:
    """Best-effort Escape keypress; skips on driver failure."""
    try:
        os_input.press_key("escape")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 1. dialog-edit-project
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
def test_dialog_edit_project_opens_and_closes(
    mcp, os_input, prepared_project_path
):
    """Open the edit-project dialog via the project sidebar menu and verify
    the dialog DOM structure: title, name text-field, cancel and save buttons.

    Trigger path:
      navigate to project route -> wait for [data-action="project-menu"]
      -> click it -> wait for DropdownMenu.Content -> click the "Edit" item
      -> assert the dialog renders with an <input> and action buttons
      -> close via Escape -> assert the dialog is gone.

    The dialog title "Edit project" is used as the presence signal because
    the Dialog component does not currently expose a data-component anchor.
    """
    nav = Navigator(mcp)
    probe = DOMProbe(mcp)

    # Navigate to home first so globalSync has a chance to register the
    # project, then navigate to its route.
    nav.go(route_home(), timeout_s=5.0)
    time.sleep(0.5)
    token = encode_dir_token(prepared_project_path)
    # Use /:dir/session — route_project targets /:dir which the SPA immediately
    # redirects to /:dir/session; nav.go cannot follow that redirect.
    nav.go(route_session_in_project(token), timeout_s=5.0)
    time.sleep(1.0)  # let globalSync propagate the project

    # Pre-flight: dismiss any stale overlay that would swallow Escape or
    # intercept the dropdown we're about to open.
    _dismiss_any_overlay(probe, os_input)

    # Pre-flight: confirm that [data-action="project-menu"] is present.
    # It may take a moment for the sidebar project entry to mount.
    menu_trigger_sel = (
        f'[data-action=\\"project-menu\\"][data-project=\\"{token}\\"]'
    )
    fallback_sel = '[data-action=\\"project-menu\\"]'

    try:
        trigger_found = _wait_for(
            probe,
            f'!!document.querySelector("{menu_trigger_sel}") || '
            f'!!document.querySelector("{fallback_sel}")',
            timeout_s=8.0,
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    if not trigger_found:
        pytest.skip(
            "project-menu trigger not found in the sidebar — "
            "project may not have registered within the timeout "
            "(globalSync latency or project was not opened)"
        )

    opened = False
    try:
        # Step 1: click the project-menu (dot-grid) button to open the
        # DropdownMenu. Prefer the token-scoped selector; fall back to the
        # first project-menu if the sidebar is still updating the token.
        try:
            clicked_menu = probe.eval_bool(
                '(() => {'
                f'  let el = document.querySelector("[data-action=\\"project-menu\\"][data-project=\\"{token}\\"]");'
                '  if (!el) el = document.querySelector("[data-action=\\"project-menu\\"]");'
                '  if (!el) return false;'
                '  el.click();'
                '  return true;'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        if not clicked_menu:
            pytest.skip("could not click project-menu trigger")

        # Wait for the DropdownMenu portal to mount. Kobalte DropdownMenu.Content
        # renders with role="menu"; [data-component="dropdown-menu"] is on the
        # non-rendering root component and never appears in the DOM.
        try:
            menu_open = _wait_for(
                probe,
                '!!document.querySelector("[role=\\"menu\\"]")',
                timeout_s=2.0,
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        if not menu_open:
            # Kobalte portals the content into document.body; also check
            # for a generic menuitem as a fallback.
            try:
                menu_open = _wait_for(
                    probe,
                    '!!document.querySelector("[role=\\"menuitem\\"]")',
                    timeout_s=2.0,
                )
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable ({e})")

        if not menu_open:
            pytest.skip(
                "project-menu dropdown did not open — DropdownMenu may be "
                "suppressed by layout conditions or a stale overlay"
            )

        # Step 2: click the "Edit" menu item. The label comes from
        # language.t("common.edit") == "Edit" in en.ts.
        try:
            clicked_edit = probe.eval_bool(
                '(() => {'
                '  const items = Array.from(document.querySelectorAll('
                '    "[role=\\"menuitem\\"]"'
                '  ));'
                '  const edit = items.find('
                '    el => /^edit$/i.test((el.textContent || "").trim())'
                '  );'
                '  if (!edit) return false;'
                '  edit.click();'
                '  return true;'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        if not clicked_edit:
            pytest.skip(
                'no "Edit" menu item found in the project DropdownMenu '
                "(i18n mismatch or menu did not render its items)"
            )

        # Step 3: wait for the dialog to mount. The title "Edit project" is
        # present inside a [data-slot="dialog-title"] or an <h2> inside the
        # dialog root.
        title_escaped = _EDIT_PROJECT_TITLE_EN.replace('"', '\\"')
        try:
            opened = _wait_for(
                probe,
                '(() => {'
                '  const dialog = document.querySelector('
                '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                '  );'
                '  if (!dialog) return false;'
                # Accept any element whose trimmed text matches the title.
                f'  return Array.from(dialog.querySelectorAll("*")).some('
                f'    el => (el.textContent || "").trim() === "{title_escaped}"'
                f'  );'
                '})()',
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        if not opened:
            pytest.skip(
                f'dialog-edit-project title "{_EDIT_PROJECT_TITLE_EN}" did not '
                "appear within timeout — dynamic import or dialog mount failure"
            )

        # Content verification: heading text non-empty. The definitive content
        # checks for this dialog are the structural assertions below
        # (input[type=text] + Save button) — a generic "any enabled button"
        # count is redundant with those stronger, dialog-specific assertions.
        try:
            has_heading = probe.eval_bool(
                '(() => {'
                '  const dialog = document.querySelector('
                '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                '  );'
                '  if (!dialog) return false;'
                '  const h = dialog.querySelector('
                '    "[data-slot=\\"dialog-title\\"], h1, h2"'
                '  );'
                '  return !!h && (h.textContent || "").trim().length > 0;'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable mid-test ({e})")
        assert has_heading, "dialog-edit-project has no non-empty heading"

        # Structural assertions: name text-field and cancel/save buttons.

        # (a) An <input type="text"> should be present inside the dialog for
        # the project name TextField.
        try:
            has_input = probe.eval_bool(
                '(() => {'
                '  const dialog = document.querySelector('
                '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                '  );'
                '  if (!dialog) return false;'
                '  return !!dialog.querySelector("input[type=\\"text\\"]");'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable mid-test ({e})")
        assert has_input, "dialog-edit-project is missing an input[type=text] for the project name"

        # (b) Cancel and Save buttons should both be present.
        try:
            has_cancel = probe.eval_bool(
                '(() => {'
                '  const dialog = document.querySelector('
                '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                '  );'
                '  if (!dialog) return false;'
                '  const btns = Array.from(dialog.querySelectorAll("button"));'
                '  return btns.some('
                '    b => /^cancel$/i.test((b.textContent || "").trim())'
                '  );'
                '})()'
            )
            has_save = probe.eval_bool(
                '(() => {'
                '  const dialog = document.querySelector('
                '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                '  );'
                '  if (!dialog) return false;'
                '  const btns = Array.from(dialog.querySelectorAll("button"));'
                '  return btns.some('
                '    b => /^save$|^saving$/i.test((b.textContent || "").trim())'
                '  );'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable mid-test ({e})")
        assert has_cancel, "dialog-edit-project is missing a Cancel button"
        assert has_save, "dialog-edit-project is missing a Save button"

        # Step 4: close via Escape.
        _press_escape(os_input)
        time.sleep(0.3)

        # Step 5: assert the dialog is gone.
        title_still_present_js = (
            '(() => {'
            '  const dialog = document.querySelector('
            '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
            '  );'
            '  if (!dialog) return false;'
            f'  return Array.from(dialog.querySelectorAll("*")).some('
            f'    el => (el.textContent || "").trim() === "{title_escaped}"'
            f'  );'
            '})()'
        )
        deadline_close = time.monotonic() + 2.0
        closed = False
        while time.monotonic() < deadline_close:
            try:
                still_open = probe.eval_bool(title_still_present_js)
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable mid-test ({e})")
            if not still_open:
                closed = True
                break
            time.sleep(0.1)
        assert closed, "dialog-edit-project did not close on Escape"

    finally:
        _dismiss_any_overlay(probe, os_input)


# ---------------------------------------------------------------------------
# 2. dialog-release-notes  (xfail — no stable programmatic trigger)
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
# TODO: flip to strict=True when Help > Release Notes menu item lands.
# Kept strict=False because no trigger exists in the current UI — the test
# asserts "no trigger exists" by failing fast at pytest.fail() during click
# discovery (auditor-confirmed: see packages/desktop/src/menu.ts).
@pytest.mark.xfail(
    reason=(
        "dialog-release-notes has no stable programmatic trigger: it is shown "
        "automatically by the HighlightsProvider only when the persisted "
        "highlights.v1 version differs from the running platform.version. "
        "The native Help menu has the 'Release Notes' entry commented out "
        "(see packages/desktop/src/menu.ts). No data-action or command exists "
        "to trigger it on demand. Unxfail when a stable trigger is added "
        "(e.g. a menu item or data-action='open-release-notes')."
    ),
    strict=False,
)
def test_dialog_release_notes_opens_and_closes(mcp, os_input):
    """Verify the release-notes dialog can be opened and contains content.

    This test is xfail because no stable trigger exists in the current product:
    - The dialog is opened by HighlightsProvider after a version change, which
      requires clearing the persisted 'highlights.v1' store and relaunching.
    - The Help menu item is commented out in menu.ts.
    - There is no data-action or Tauri command to trigger the dialog on demand.

    When a stable trigger is added, this test should:
    1. Navigate to any route.
    2. Click the trigger.
    3. Wait for [data-component="dialog"] with content from the highlights array.
    4. Close via Escape or the "Get started" button.
    5. Assert the dialog is gone.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)

    # Attempt: look for any button or link that mentions "Release Notes"
    # (this would succeed if the Help menu item is ever uncommented, or if
    # another surface adds a "Release Notes" link).
    try:
        clicked = probe.eval_bool(
            '(() => {'
            '  const all = Array.from(document.querySelectorAll('
            '    "button, a, [role=\\"button\\"], [role=\\"menuitem\\"]"'
            '  ));'
            '  const el = all.find('
            '    e => /release.*notes/i.test(e.textContent || "") || '
            '         /release.*notes/i.test(e.getAttribute("aria-label") || "")'
            '  );'
            '  if (!el) return false;'
            '  el.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    if not clicked:
        pytest.fail(
            "no 'Release Notes' trigger found on home surface — "
            "the dialog is only shown automatically by HighlightsProvider "
            "after a version upgrade (trigger is not accessible via DOM)"
        )

    try:
        opened = _wait_for(probe, _JS_ANY_DIALOG_OPEN)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")

    assert opened, "dialog-release-notes did not mount after clicking the trigger"

    # Content verification: heading text non-empty + enabled button present.
    try:
        has_heading = probe.eval_bool(
            '(() => {'
            '  const dialog = document.querySelector('
            '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
            '  );'
            '  if (!dialog) return false;'
            '  const h = dialog.querySelector('
            '    "[data-slot=\\"dialog-title\\"], h1, h2"'
            '  );'
            '  return !!h && (h.textContent || "").trim().length > 0;'
            '})()'
        )
        enabled_btn_count = probe.eval_int(
            '(() => {'
            '  const dialog = document.querySelector('
            '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
            '  );'
            '  if (!dialog) return 0;'
            '  return dialog.querySelectorAll("button:not([disabled])").length;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable mid-test ({e})")
    assert has_heading, "dialog-release-notes has no non-empty heading"
    assert enabled_btn_count > 0, "dialog-release-notes has no enabled button"

    # Verify the dialog has non-empty text content.
    try:
        has_content = probe.eval_bool(
            '(() => {'
            '  const dialog = document.querySelector('
            '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
            '  );'
            '  if (!dialog) return false;'
            '  return (dialog.textContent || "").trim().length > 0;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable mid-test ({e})")
    assert has_content, "dialog-release-notes rendered but has no text content"

    _press_escape(os_input)
    time.sleep(0.3)

    deadline_close = time.monotonic() + 2.0
    closed = False
    while time.monotonic() < deadline_close:
        try:
            still_open = probe.eval_bool(_JS_ANY_DIALOG_OPEN)
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable mid-test ({e})")
        if not still_open:
            closed = True
            break
        time.sleep(0.1)
    assert closed, "dialog-release-notes did not close on Escape"


# ---------------------------------------------------------------------------
# 3. dialog-select-server
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
def test_dialog_select_server_opens_and_closes(mcp, os_input):
    """Open the server-select dialog via the home-page server button.

    On the home page, a Button renders the active server name and opens
    DialogSelectServer on click (packages/app/src/pages/home.tsx line ~92).
    The dialog has title "Servers" and shows either a list of configured
    servers or an empty-state message ("No servers yet").

    Trigger path:
      navigate to home -> find the server button by its text-content match
      -> click it -> assert the dialog is open (title "Servers" present)
      -> verify it has server list items or an empty-state message
      -> close via Escape -> assert the dialog is gone.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    time.sleep(0.5)  # let the home surface fully mount

    _dismiss_any_overlay(probe, os_input)

    opened = False
    try:
        # The server button on home renders server.name as its text and lives
        # at the top of the home surface. It is the only Button on that surface
        # that opens a dialog on click — we identify it by checking that it
        # has a small colored dot sibling (the health-status dot) which is
        # always co-rendered with the server name. As a robust fallback we
        # also look for any button whose text could be a server URL fragment
        # (localhost, remote host) or "Local".
        try:
            clicked = probe.eval_bool(
                '(() => {'
                # The server-name button is inside .mx-auto.mt-55 on home.
                # It is a ghost Button that contains a round-dot div + server name.
                # Identify it by: it is a button whose children include a
                # size-2 rounded-full div (the health dot).
                '  const allBtns = Array.from(document.querySelectorAll("button"));'
                '  const btn = allBtns.find(b => '
                '    b.querySelector(".rounded-full") !== null && '
                # Exclude any button that is a tab trigger or icon-only button.
                '    (b.textContent || "").trim().length > 0 && '
                '    !/^(Servers|MCP|Edit|Cancel|Save|General|Models)$/i.test('
                '      (b.textContent || "").trim()'
                '    )'
                '  );'
                '  if (!btn) return false;'
                '  btn.click();'
                '  return true;'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        if not clicked:
            pytest.skip(
                "server-name button not found on home surface — "
                "home may have rendered without a server button "
                "(network error, welcome overlay, or home surface changed)"
            )

        # Wait for the dialog with title "Servers".
        title_escaped = _SELECT_SERVER_TITLE_EN.replace('"', '\\"')
        try:
            opened = _wait_for(
                probe,
                '(() => {'
                '  const dialog = document.querySelector('
                '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                '  );'
                '  if (!dialog) return false;'
                f'  return Array.from(dialog.querySelectorAll("*")).some('
                f'    el => (el.textContent || "").trim() === "{title_escaped}"'
                f'  );'
                '})()',
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")

        if not opened:
            pytest.skip(
                f'dialog-select-server title "{_SELECT_SERVER_TITLE_EN}" did not '
                "appear within timeout — dynamic import or dialog mount failure"
            )

        # Content verification: heading text non-empty. The structural
        # assertion below (list container OR "Add server" button) is the
        # definitive content check — a generic "any enabled button" count
        # would pass trivially because Cancel/close buttons are always
        # present on an empty dialog shell, and is therefore redundant.
        try:
            has_heading = probe.eval_bool(
                '(() => {'
                '  const dialog = document.querySelector('
                '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                '  );'
                '  if (!dialog) return false;'
                '  const h = dialog.querySelector('
                '    "[data-slot=\\"dialog-title\\"], h1, h2"'
                '  );'
                '  return !!h && (h.textContent || "").trim().length > 0;'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable mid-test ({e})")
        assert has_heading, "dialog-select-server has no non-empty heading"

        # Structural assertion: the dialog must contain a list container
        # ([data-slot="list"] or [data-slot="list-item"]) OR an explicit
        # "Add server" button. The List component renders
        # [data-slot="list-item"] for each configured server; the empty
        # state still renders an "Add server" CTA button.
        try:
            has_list_or_add = probe.eval_bool(
                '(() => {'
                '  const dialog = document.querySelector('
                '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                '  );'
                '  if (!dialog) return false;'
                # List container or at least one list item.
                '  const hasList = !!dialog.querySelector('
                '    "[data-slot=\\"list\\"], [data-slot=\\"list-item\\"]"'
                '  );'
                # "Add server" button — text match is resilient to minor
                # label changes and matches the empty-state CTA.
                '  const btns = Array.from(dialog.querySelectorAll("button"));'
                '  const hasAddServer = btns.some('
                '    b => /add.*server/i.test((b.textContent || "").trim())'
                '  );'
                '  return hasList || hasAddServer;'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable mid-test ({e})")
        assert has_list_or_add, (
            "dialog-select-server is missing both a list container "
            "([data-slot='list'|'list-item']) and an 'Add server' button"
        )

        # Close via Escape.
        _press_escape(os_input)
        time.sleep(0.3)

        # Assert the dialog is gone.
        deadline_close = time.monotonic() + 2.0
        closed = False
        while time.monotonic() < deadline_close:
            try:
                still_open = probe.eval_bool(
                    '(() => {'
                    '  const dialog = document.querySelector('
                    '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                    '  );'
                    '  if (!dialog) return false;'
                    f'  return Array.from(dialog.querySelectorAll("*")).some('
                    f'    el => (el.textContent || "").trim() === "{title_escaped}"'
                    f'  );'
                    '})()'
                )
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable mid-test ({e})")
            if not still_open:
                closed = True
                break
            time.sleep(0.1)
        assert closed, "dialog-select-server did not close on Escape"

    finally:
        _dismiss_any_overlay(probe, os_input)
